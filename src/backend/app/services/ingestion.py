"""One upload worker, with durable task state and no demo fallbacks."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
from sqlalchemy import update
from src.backend.app.models.database import IngestionTask, DocumentRecord, FileArtifact
from src.backend.app.services import ocr_revisions

def _describe_failure(exc: BaseException, last_status: str | None) -> str:
    from labor_rag.services.ingestion import IngestionInputError
    if isinstance(exc, IngestionInputError):
        return str(exc)
    exc_name = type(exc).__name__
    module = (type(exc).__module__ or "").lower()
    if module.startswith("modal"):
        if exc_name == "AuthError":
            return "Lỗi xác thực Modal (AuthError): Chưa đăng nhập hoặc thiếu MODAL_TOKEN_ID / MODAL_TOKEN_SECRET."
        if exc_name == "NotFoundError":
            return "Không tìm thấy ứng dụng Modal (NotFoundError): Chưa deploy app hoặc sai MODAL_APP_NAME (chạy 'modal deploy scripts/modal_embed.py')."
        return f"Lỗi dịch vụ GPU Modal ({exc_name}). Kiểm tra cấu hình Modal hoặc chuyển sang local."
    if module.startswith("neo4j"):
        if exc_name == "AuthError":
            return "Lỗi xác thực Neo4j Aura (AuthError): Kiểm tra lại NEO4J_USER và NEO4J_PASSWORD."
        return f"Lỗi kết nối cơ sở dữ liệu đồ thị Neo4j ({exc_name})."
    if module.startswith("qdrant_client"):
        return f"Lỗi kho dữ liệu vector Qdrant ({exc_name}). Kiểm tra QDRANT_URL, QDRANT_API_KEY và tên collection."
    if module.startswith("botocore") or module.startswith("boto3"):
        return f"Lỗi lưu trữ Cloudflare R2 ({exc_name}). Kiểm tra cấu hình R2."
    stage_names = {
        "pending": "Khởi tạo",
        "parsing": "Đọc & OCR",
        "chunking": "Tách cấu trúc",
        "embedding": "Tạo vector tìm kiếm",
        "indexing": "Đồng bộ kho dữ liệu",
    }
    stage = stage_names.get(last_status or "", "Xử lý")
    return f"Nạp tài liệu chưa hoàn tất tại bước {stage} ({exc_name}). Có thể nạp lại để tiếp tục."


class IngestionService:
    def __init__(self, runtime, database):
        self.runtime, self.database = runtime, database
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="legal-ingestion")
        self._cancel_lock = threading.Lock()
        self._cancel_events: dict[str, threading.Event] = {}
        self._ocr_lock = threading.Lock()
        self._ocr_previews: dict[str, dict] = {}

    def recover_interrupted(self):
        if self.database.available:
            with self.database.session() as db:
                db.execute(update(IngestionTask).where(IngestionTask.status.notin_(["completed", "failed", "cancelled", "awaiting_review"]))
                    .values(status="failed", current_step="Backend đã khởi động lại; cần nạp lại file.",
                            error_message="interrupted_by_restart"))
                db.commit()

    def is_cancelled(self, task_id: str) -> bool:
        with self._cancel_lock:
            event = self._cancel_events.get(task_id)
            return event.is_set() if event else False

    def cancel(self, task_id: str):
        with self._cancel_lock:
            event = self._cancel_events.get(task_id)
            if event is not None:
                event.set()
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return None
            if task.status in {"completed", "failed", "cancelled"}:
                return task
            if task.status == "awaiting_review" and ocr_revisions.discard_draft(db, task_id):
                # A reopened task: drop the draft, the indexed revision and the corpus stay as they were.
                task.status, task.progress = "completed", 100.0
                task.current_step = "Đã bỏ bản nháp; văn bản trong kho giữ nguyên bản đang dùng."
                db.commit()
                db.refresh(task)
                return task
            if task.status in {"pending", "awaiting_review"}:
                task.status = "cancelled"
                task.current_step = "Đã hủy nạp tài liệu theo yêu cầu người dùng."
                with self._cancel_lock:
                    self._cancel_events.pop(task_id, None)
            else:
                task.current_step = "Đang hủy tiến trình theo yêu cầu..."
            db.commit()
            db.refresh(task)
            return task

    def submit(self, task_id, file_path, document_type, de_muc_id=None, domain="lao_dong", pause_for_review=True):
        # Reserve a config snapshot for both queued and running uploads.
        target = self._run_extract_phase if (document_type == "pdf" and pause_for_review) else self._run
        with self._cancel_lock:
            self._cancel_events[task_id] = threading.Event()
        with self.runtime.lock:
            self.runtime.active += 1
        try:
            self.executor.submit(target, task_id, file_path, document_type, de_muc_id, domain)
        except Exception:
            with self._cancel_lock:
                self._cancel_events.pop(task_id, None)
            with self.runtime.lock:
                self.runtime.active -= 1
            raise

    def _progress(self, task_id, value, status, step, **fields):
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task:
                if value is not None:
                    task.progress = value
                task.status, task.current_step = status, step
                for key, val in fields.items():
                    if hasattr(task, key):
                        setattr(task, key, val)
                db.commit()

    def record_ocr_page(self, task_id: str, page_info: dict):
        with self._ocr_lock:
            state = self._ocr_previews.get(task_id)
            if state is None:
                if len(self._ocr_previews) >= 20:
                    oldest = next(iter(self._ocr_previews))
                    self._ocr_previews.pop(oldest, None)
                state = {
                    "total_pages": int(page_info.get("total_pages") or 0),
                    "processed_pages": 0,
                    "text_pages": 0,
                    "ocr_pages": 0,
                    "empty_pages": 0,
                    "_conf_sum": 0.0,
                    "_conf_count": 0,
                    "avg_confidence": None,
                    "heuristic_score": None,
                    "articles_count": None,
                    "warnings": [],
                    "recent_pages": [],
                }
                self._ocr_previews[task_id] = state
            state["total_pages"] = max(state["total_pages"], int(page_info.get("total_pages") or 0))
            state["processed_pages"] += 1
            method = page_info.get("method")
            if method == "text":
                state["text_pages"] += 1
            elif method == "ocr":
                state["ocr_pages"] += 1
            else:
                state["empty_pages"] += 1
            conf = page_info.get("confidence")
            if conf is not None:
                state["_conf_sum"] += float(conf)
                state["_conf_count"] += 1
                state["avg_confidence"] = round(state["_conf_sum"] / state["_conf_count"], 4)
            state["recent_pages"].append({
                "page_number": int(page_info["page_number"]),
                "method": str(method or "unknown"),
                "confidence": conf,
                "char_count": int(page_info.get("char_count") or 0),
                "preview_text": str(page_info.get("preview_text") or ""),
            })
            if len(state["recent_pages"]) > 30:
                state["recent_pages"] = state["recent_pages"][-30:]

    def finalize_ocr_summary(self, task_id: str, summary: dict):
        if not summary:
            return
        with self._ocr_lock:
            state = self._ocr_previews.get(task_id)
            if state is None:
                state = {
                    "total_pages": summary.get("total_pages", 0),
                    "processed_pages": summary.get("total_pages", 0),
                    "text_pages": summary.get("text_pages", 0),
                    "ocr_pages": summary.get("ocr_pages", 0),
                    "empty_pages": summary.get("empty_pages", 0),
                    "avg_confidence": summary.get("avg_confidence"),
                    "heuristic_score": summary.get("heuristic_score"),
                    "articles_count": summary.get("articles_count"),
                    "warnings": list(summary.get("warnings") or []),
                    "recent_pages": [],
                }
                self._ocr_previews[task_id] = state
            else:
                state["heuristic_score"] = summary.get("heuristic_score")
                state["articles_count"] = summary.get("articles_count")
                state["warnings"] = list(summary.get("warnings") or [])
                if summary.get("avg_confidence") is not None:
                    state["avg_confidence"] = summary["avg_confidence"]

    def get_ocr_preview(self, task_id: str) -> dict | None:
        with self._ocr_lock:
            state = self._ocr_previews.get(task_id)
            if state is not None:
                return {
                    "total_pages": state["total_pages"],
                    "processed_pages": state["processed_pages"],
                    "text_pages": state["text_pages"],
                    "ocr_pages": state["ocr_pages"],
                    "empty_pages": state["empty_pages"],
                    "avg_confidence": state["avg_confidence"],
                    "heuristic_score": state["heuristic_score"],
                    "articles_count": state["articles_count"],
                    "warnings": list(state["warnings"]),
                    "recent_pages": list(state["recent_pages"]),
                }
        entries = self.revision_pages(task_id)
        if not entries:
            return None
        confs = [float(e["confidence"]) for e in entries if e.get("confidence") is not None]
        return {
            "total_pages": max((int(e.get("total_pages") or 0) for e in entries), default=len(entries)),
            "processed_pages": len(entries),
            "text_pages": sum(1 for e in entries if e.get("method") == "text"),
            "ocr_pages": sum(1 for e in entries if e.get("method") == "ocr"),
            "empty_pages": sum(1 for e in entries if e.get("method") not in {"text", "ocr"}),
            "avg_confidence": round(sum(confs) / len(confs), 4) if confs else None,
            "heuristic_score": None,
            "articles_count": None,
            "warnings": [],
            "recent_pages": [{
                "page_number": int(e["page_number"]),
                "method": str(e.get("method") or "unknown"),
                "confidence": e.get("confidence"),
                "char_count": int(e.get("char_count") or 0),
                "preview_text": str(e.get("text") or "")[:600].strip(),
            } for e in entries[-30:]],
        }

    # ------------------------------------------------------------------
    # OCR revisions (services/ocr_revisions.py)
    # ------------------------------------------------------------------

    def _pages_file_entries(self, task_id: str) -> list[dict]:
        from labor_rag.services.ingestion import read_pages_file
        return read_pages_file(self.runtime.settings.INTERIM_DIR / "ingestion" / task_id)

    def _ensure_revisions(self, db, task: IngestionTask) -> None:
        """Tasks from before revisions existed: import ocr_pages.jsonl once."""
        if task.document_type != "pdf" or ocr_revisions.revisions(db, task.id):
            return
        entries = self._pages_file_entries(task.id)
        if entries:
            ocr_revisions.import_pages(db, task.id, entries, indexed=task.status == "completed",
                                       document_id=task.document_id)
            db.commit()

    def revision_pages(self, task_id: str, revision_id: str | None = None) -> list[dict]:
        """Page entries of a revision (default: the draft, else the indexed one); [] when unknown."""
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return []
            self._ensure_revisions(db, task)
            revision = ocr_revisions.get(db, task_id, revision_id)
            return ocr_revisions.pages(db, revision) if revision else []

    def list_revisions(self, task_id: str) -> list | None:
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return None
            self._ensure_revisions(db, task)
            rows = ocr_revisions.revisions(db, task_id)
            return [{"id": r.id, "number": r.number, "kind": r.kind, "status": r.status, "parent_id": r.parent_id,
                     "document_id": r.document_id, "created_at": r.created_at, "updated_at": r.updated_at,
                     "indexed_at": r.indexed_at, **ocr_revisions.summary(db, r)} for r in rows]

    def list_tasks(self, *, state: str | None = None, document_id: str | None = None,
                   cursor: tuple[str, str] | None = None, limit: int = 20) -> tuple[list[dict], int, bool]:
        """(rows, total, has_more), newest first, with a state label per task (ocr_revisions.task_state)."""
        with self.database.session() as db:
            query = db.query(IngestionTask)
            if document_id:
                query = query.filter(IngestionTask.document_id == document_id)
            tasks = query.order_by(IngestionTask.created_at.desc(), IngestionTask.id.desc()).all()
            in_corpus = {row[0] for row in db.query(DocumentRecord.id).all()}
            rows = []
            for task in tasks:
                self._ensure_revisions(db, task)
                draft = ocr_revisions.by_status(db, task.id, "draft")
                indexed = ocr_revisions.by_status(db, task.id, "indexed")
                doc_id = task.document_id or (indexed.document_id if indexed else None)
                label = ocr_revisions.task_state(task, draft, indexed, doc_id in in_corpus if doc_id else False)
                if state and label != state:
                    continue
                record = db.get(DocumentRecord, doc_id) if doc_id else None
                meta = task.result if isinstance(task.result, dict) else {}
                rows.append({"id": task.id, "file_name": task.file_name, "document_type": task.document_type,
                             "status": task.status, "state": label, "progress": task.progress,
                             "current_step": task.current_step, "document_id": doc_id,
                             "document_number": record.document_number if record else None,
                             "domain": meta.get("domain"), "in_corpus": bool(record),
                             "draft_revision_id": draft.id if draft else None,
                             "indexed_revision_id": indexed.id if indexed else None,
                             **ocr_revisions.summary(db, draft or indexed),
                             "created_at": task.created_at, "updated_at": task.updated_at})
        total = len(rows)
        if cursor:
            stamp, last_id = cursor
            rows = [r for r in rows if (r["created_at"].isoformat(), r["id"]) < (stamp, last_id)]
        return rows[:limit], total, len(rows) > limit

    def reopen(self, task_id: str, from_revision_id: str | None = None):
        """(task, state): a new draft copied from a revision, so an indexed or removed document can be
        corrected and re-indexed without OCR. The corpus is untouched until the draft is confirmed."""
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return None, "not_found"
            if task.document_type != "pdf":
                return task, "not_pdf"
            if task.status in {"pending", "parsing", "chunking", "embedding", "indexing"}:
                return task, "busy"
            self._ensure_revisions(db, task)
            try:
                draft = ocr_revisions.new_draft(db, task_id, from_revision_id)
            except ocr_revisions.DraftExists:
                return task, "draft_exists"
            except LookupError:
                return task, "no_revision"
            task.status, task.progress = "awaiting_review", 30.0
            task.current_step = f"Đang sửa bản rà soát {draft.number}; bấm 'Nạp lại' khi xong."
            task.error_message = None
            db.commit()
            db.refresh(task)
            return task, "ok"

    def get_ocr_page_text(self, task_id: str, page_number: int, revision_id: str | None = None) -> dict | None:
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return None
            self._ensure_revisions(db, task)
            revision = ocr_revisions.get(db, task_id, revision_id)
            entry = ocr_revisions.page(db, revision, page_number) if revision else None
        if entry is None:
            # Still running: the page is in the per-page file, revisions come when OCR ends.
            entry = next((e for e in self._pages_file_entries(task_id) if int(e.get("page_number") or 0) == page_number), None)
        if entry is None:
            return None
        return {"page_number": page_number, "method": str(entry.get("method") or "unknown"),
                "confidence": entry.get("confidence"), "char_count": int(entry.get("char_count") or 0),
                "text": str(entry.get("text") or "")}

    def _resolve_task_pdf_path(self, task_id: str, task: IngestionTask | None = None) -> Path | None:
        path = self._local_task_pdf(task_id, task)
        if path is None and task is not None:
            path = self._restore_task_pdf(task_id, task)
        return path

    def _snapshot_revision(self, task_id: str, revision_id: str | None) -> None:
        """A fixed copy of the indexed review's pages on R2, in case the database is lost."""
        if not revision_id:
            return
        from labor_rag.services.ingestion import store_artifact
        pages = self.revision_pages(task_id, revision_id)
        with self.database.session() as db:
            revision = ocr_revisions.get(db, task_id, revision_id)
            task = db.get(IngestionTask, task_id)
            if revision is None or task is None or not pages:
                return
            path = self.runtime.settings.INTERIM_DIR / "ingestion" / task_id / f"revision-{revision.number}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("".join(json.dumps(page, ensure_ascii=False) + "\n" for page in pages), encoding="utf-8")
            try:
                artifact = store_artifact(path, self.runtime.storage(), "ocr_pages")
            except Exception as exc:
                meta = dict(task.result or {})
                meta["warnings"] = [*meta.get("warnings", []), f"Chưa sao lưu được bản rà soát lên R2 ({type(exc).__name__})."]
                task.result = meta
                db.commit()
                return
            if db.get(FileArtifact, artifact["artifact_id"]) is None:
                db.add(FileArtifact(id=artifact["artifact_id"], record=artifact))
            revision.snapshot_artifact_id = artifact["artifact_id"]
            db.commit()

    def delete_task(self, task_id: str) -> str:
        """Delete an upload with its OCR revisions and local files.

        Refused while it runs, and while the document it indexed is still in the
        corpus with this upload as its latest source (remove the document first).
        R2 objects stay: they are content addressed and may be shared.
        """
        import shutil
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return "not_found"
            if task.status in {"pending", "parsing", "chunking", "embedding", "indexing"}:
                return "busy"
            indexed = ocr_revisions.by_status(db, task_id, "indexed")
            document_id = (indexed.document_id if indexed else None) or (task.document_id if task.status == "completed" else None)
            if document_id and db.get(DocumentRecord, document_id) is not None:
                newer = (db.query(IngestionTask).filter(IngestionTask.document_id == document_id,
                                                        IngestionTask.id != task_id,
                                                        IngestionTask.status == "completed",
                                                        IngestionTask.created_at > task.created_at).first())
                if newer is None:
                    return "in_corpus"
            # Children first, as plain statements, so the order never depends on the ORM.
            revision_ids = [r.id for r in ocr_revisions.revisions(db, task_id)]
            if revision_ids:
                db.query(ocr_revisions.OcrPage).filter(ocr_revisions.OcrPage.revision_id.in_(revision_ids))                     .delete(synchronize_session=False)
            db.query(ocr_revisions.OcrRevision).filter(ocr_revisions.OcrRevision.task_id == task_id)                 .delete(synchronize_session=False)
            db.query(IngestionTask).filter(IngestionTask.id == task_id).delete(synchronize_session=False)
            db.commit()
        settings = self.runtime.settings
        for base in (settings.INTERIM_DIR / "ingestion", settings.UPLOAD_DIR):
            root = base.resolve()
            target = (root / task_id).resolve()
            if target != root and target.is_relative_to(root) and target.exists():
                shutil.rmtree(target, ignore_errors=True)
        with self._ocr_lock:
            self._ocr_previews.pop(task_id, None)
        return "ok"

    def _restore_task_pdf(self, task_id: str, task: IngestionTask) -> Path | None:
        """The source PDF from R2 when this machine no longer has it (another server, cleaned uploads)."""
        meta = task.result if isinstance(task.result, dict) else {}
        artifact_id = meta.get("source_artifact_id") or next(iter(meta.get("artifact_ids") or []), None)
        if not artifact_id:
            return None
        with self.database.session() as db:
            row = db.get(FileArtifact, artifact_id)
            record = dict(row.record) if row else None
        if not record or not str(record.get("file_name", "")).lower().endswith(".pdf"):
            return None
        upload_root = self.runtime.settings.UPLOAD_DIR.resolve()
        dest = (upload_root / task_id / Path(record["file_name"]).name).resolve()
        if not dest.is_relative_to(upload_root):
            return None
        try:
            return self.runtime.storage().download_verified(record, dest)
        except Exception:
            return None

    def _local_task_pdf(self, task_id: str, task: IngestionTask | None = None) -> Path | None:
        upload_root = self.runtime.settings.UPLOAD_DIR.resolve()
        candidate: Path | None = None
        if task and isinstance(task.result, dict) and task.result.get("file_path"):
            p = Path(task.result["file_path"]).resolve()
            if p.is_relative_to(upload_root) and p.exists():
                candidate = p
        if candidate is None:
            task_dir = (upload_root / task_id).resolve()
            if task_dir.is_relative_to(upload_root) and task_dir.exists():
                pdfs = sorted(task_dir.glob("*.pdf"))
                if pdfs:
                    candidate = pdfs[0]
        return candidate

    def get_pdf_page_image(self, task_id: str, page_number: int) -> bytes | None:
        if page_number < 1:
            return None
        cache_dir = self.runtime.settings.INTERIM_DIR / "ingestion" / task_id / "page_images"
        cache_file = cache_dir / f"page_{page_number}.png"
        if cache_file.exists():
            return cache_file.read_bytes()
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None or task.document_type != "pdf":
                return None
            pdf_path = self._resolve_task_pdf_path(task_id, task)
        if pdf_path is None:
            return None
        import pymupdf
        with pymupdf.open(pdf_path) as doc:
            if page_number > doc.page_count:
                return None
            pixmap = doc[page_number - 1].get_pixmap(dpi=150)
            png_bytes = pixmap.tobytes("png")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(png_bytes)
        return png_bytes

    def update_ocr_page_text(self, task_id: str, page_number: int, text: str, revision_id: str | None = None) -> dict | None:
        """Edit a page of the draft; raises ocr_revisions.RevisionLocked for other revisions."""
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return None
            self._ensure_revisions(db, task)
            revision = ocr_revisions.get(db, task_id, revision_id)
            if revision is None:
                return None
            entry = ocr_revisions.set_page_text(db, revision, page_number, text)
            db.commit()
        if entry is None:
            return None
        updated_entry = {"page_number": page_number, "method": str(entry.get("method") or "unknown"),
                         "confidence": entry.get("confidence"), "char_count": len(text), "text": text}
        with self._ocr_lock:
            state = self._ocr_previews.get(task_id)
            if state is not None:
                for item in state.get("recent_pages", []):
                    if item.get("page_number") == page_number:
                        item["char_count"] = len(text)
                        item["preview_text"] = text[:600].strip()
                        break
        return updated_entry

    def preview_changes(self, task_id: str):
        """(changes, state): what confirming this task would write; nothing is written."""
        from labor_rag.services.changes import preview_changes
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return None, "not_found"
            if task.status != "awaiting_review":
                return None, "invalid_state"
            meta = task.result if isinstance(task.result, dict) else {}
            pdf_path = self._resolve_task_pdf_path(task_id, task)
            domain = str(meta.get("domain") or "lao_dong")
            self._ensure_revisions(db, task)
            draft = ocr_revisions.by_status(db, task_id, "draft")
            pages = ocr_revisions.pages(db, draft) if draft else None
        if pdf_path is None:
            return None, "missing_file"
        with self.runtime.operation(serialized=False):
            return preview_changes(self.runtime.settings, task_id, pdf_path, domain, pages=pages), "ok"

    def remove_document(self, document_id: str):
        """(result, state): remove an indexed PDF document; Phap dien entries cannot be removed."""
        from labor_rag.services.removal import remove_pdf_document
        from src.backend.app.services.corpus import Corpus
        record_type = None
        if self.database.available:
            with self.database.session() as db:
                record = db.get(DocumentRecord, document_id)
                record_type = record.document_type if record else None
        if record_type is None:
            record_type = (Corpus().documents.get(document_id) or {}).get("document_type")
        if record_type is None:
            return None, "not_found"
        if record_type != "pdf":
            return None, "not_pdf"
        # Serialized: an upload being indexed finishes first and cannot interleave.
        with self.runtime.operation():
            result = remove_pdf_document(self.runtime.settings, document_id)
        if self.database.available:
            with self.database.session() as db:
                record = db.get(DocumentRecord, document_id)
                if record is not None:
                    db.delete(record)
                    db.commit()
        Corpus.cache_clear()
        return result, "ok"

    def confirm_review(self, task_id: str, prune: list[str] | None = None):
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task is None:
                return None, "not_found"
            if task.status != "awaiting_review":
                return task, "invalid_state"
            meta = task.result if isinstance(task.result, dict) else {}
            pdf_path = self._resolve_task_pdf_path(task_id, task)
            if pdf_path is None:
                return task, "missing_file"
            document_type = str(meta.get("document_type") or task.document_type or "pdf")
            domain = str(meta.get("domain") or "lao_dong")
            de_muc_id = meta.get("de_muc_id")
            self._ensure_revisions(db, task)
            draft = ocr_revisions.by_status(db, task_id, "draft")
            revision_id = draft.id if draft else None
            indexed = ocr_revisions.by_status(db, task_id, "indexed")
            # Re-indexing a corrected review: delete what the user confirmed, redo the graph,
            # and drop the old document if the number changed.
            reindex = ({"prune": list(prune or []), "previous_document_id": indexed.document_id or task.document_id}
                       if indexed is not None else None)
            task.status = "chunking"
            task.progress = 30.0
            task.current_step = "Đã xác nhận nội dung OCR, đang chuẩn bị lập chỉ mục..."
            task.error_message = None
            db.commit()
            db.refresh(task)

        with self._cancel_lock:
            self._cancel_events[task_id] = threading.Event()
        with self.runtime.lock:
            self.runtime.active += 1
        try:
            self.executor.submit(self._run_index_phase, task_id, pdf_path, document_type, de_muc_id, domain, revision_id, reindex)
        except Exception:
            with self._cancel_lock:
                self._cancel_events.pop(task_id, None)
            with self.runtime.lock:
                self.runtime.active -= 1
            raise
        return task, "ok"

    def _save_completion(self, task_id: str, result: dict, revision_id: str | None = None,
                         previous_document_id: str | None = None):
        from src.backend.app.services.corpus import Corpus
        with self.database.session() as db:
            for record in result["documents"]:
                existing = db.get(DocumentRecord, record["id"])
                if existing:
                    for key, value in record.items():
                        setattr(existing, key, value)
                else:
                    db.add(DocumentRecord(**record))
            if previous_document_id and previous_document_id not in result["document_ids"]:
                # The corrected number replaced the old document, which the pipeline removed.
                old = db.get(DocumentRecord, previous_document_id)
                if old is not None:
                    db.delete(old)
            for artifact in result["artifacts"]:
                row = db.get(FileArtifact, artifact["artifact_id"])
                if row:
                    row.record = artifact
                else:
                    db.add(FileArtifact(id=artifact["artifact_id"], record=artifact))
            task = db.get(IngestionTask, task_id)
            # Keep file_path / domain / de_muc_id of the upload: reopening and re-indexing need them.
            task.result = {
                **(task.result if isinstance(task.result, dict) else {}),
                "document_ids": result["document_ids"],
                "artifact_ids": [a["artifact_id"] for a in result["artifacts"]],
                "warnings": result["warnings"],
                "config_version": self.runtime.version,
                "reused_chunks": result.get("reused_chunks", 0),
                "ocr_summary": result.get("ocr_summary"),
            }
            task.document_id = result["document_ids"][0] if len(result["document_ids"]) == 1 else None
            task.status, task.progress, task.current_step = "completed", 100, "Hoàn tất! Văn bản đã sẵn sàng để xem và tra cứu."
            task.total_chunks = result["total_chunks"]
            task.embedded_chunks = result.get("embedded_chunks", result["total_chunks"])
            revision = ocr_revisions.get(db, task_id, revision_id) if revision_id else None
            if revision is not None:
                ocr_revisions.mark_indexed(db, revision, task.document_id)
            elif task.document_type == "pdf":
                # Indexed without a review pause: its OCR pages are what the corpus holds.
                ocr_revisions.import_pages(db, task_id, self._pages_file_entries(task_id), indexed=True,
                                           document_id=task.document_id)
            db.commit()
        Corpus.cache_clear()

    def _handle_failure(self, task_id: str, exc: BaseException):
        last_status = None
        try:
            with self.database.session() as db:
                existing = db.get(IngestionTask, task_id)
                if existing:
                    last_status = existing.status
        except Exception:
            last_status = None
        message = _describe_failure(exc, last_status)
        self._progress(task_id, None, "failed", message, error_message=message)

    def _cleanup_worker(self, task_id: str):
        with self._cancel_lock:
            self._cancel_events.pop(task_id, None)
        with self.runtime.lock:
            self.runtime.active -= 1

    def _run_extract_phase(self, task_id, file_path, document_type, de_muc_id, domain="lao_dong"):
        from labor_rag.services.ingestion import IngestionCancelledError, IngestionPipeline
        try:
            if self.is_cancelled(task_id):
                raise IngestionCancelledError("Đã hủy nạp tài liệu theo yêu cầu người dùng.")
            with self.runtime.operation():
                pipeline = IngestionPipeline(self.runtime.settings, self.runtime.storage())
                extracted = pipeline.extract_only(
                    file_path,
                    task_id,
                    document_type,
                    progress=lambda *args, **kwargs: self._progress(task_id, *args, **kwargs),
                    cancel_check=lambda: self.is_cancelled(task_id),
                    on_page=lambda page: self.record_ocr_page(task_id, page),
                    on_ocr_summary=lambda summary: self.finalize_ocr_summary(task_id, summary),
                )
                with self.database.session() as db:
                    task = db.get(IngestionTask, task_id)
                    if task:
                        source = extracted.get("source_artifact")
                        if source and db.get(FileArtifact, source["artifact_id"]) is None:
                            db.add(FileArtifact(id=source["artifact_id"], record=source))
                        task.result = {
                            "file_path": str(file_path),
                            "document_type": document_type,
                            "domain": domain,
                            "de_muc_id": de_muc_id,
                            "ocr_summary": extracted.get("ocr_summary"),
                            "source_artifact_id": source["artifact_id"] if source else None,
                            "warnings": ([f"Chưa sao lưu được PDF lên R2 ({extracted['source_backup_error']}); "
                                          "sẽ thử lại khi lập chỉ mục."] if extracted.get("source_backup_error") else []),
                        }
                        ocr_revisions.import_pages(db, task_id, self._pages_file_entries(task_id))
                        task.status = "awaiting_review"
                        task.progress = 30.0
                        task.current_step = "Đã OCR xong! Hãy đối chiếu, chỉnh sửa (nếu cần) rồi bấm 'Xác nhận & Lập chỉ mục'."
                        db.commit()
        except IngestionCancelledError:
            self._progress(task_id, None, "cancelled", "Đã hủy nạp tài liệu theo yêu cầu người dùng.", error_message=None)
        except (Exception, SystemExit) as exc:
            self._handle_failure(task_id, exc)
        finally:
            self._cleanup_worker(task_id)

    def _run_index_phase(self, task_id, file_path, document_type, de_muc_id, domain="lao_dong", revision_id=None, reindex=None):
        from labor_rag.services.ingestion import IngestionCancelledError, IngestionPipeline
        try:
            if self.is_cancelled(task_id):
                raise IngestionCancelledError("Đã hủy nạp tài liệu theo yêu cầu người dùng.")
            with self.runtime.operation():
                pipeline = IngestionPipeline(self.runtime.settings, self.runtime.storage())
                pages = self.revision_pages(task_id, revision_id) if revision_id else None
                result = pipeline.finalize_extracted(
                    file_path,
                    task_id,
                    document_type,
                    domain=domain,
                    de_muc_id=de_muc_id,
                    progress=lambda *args, **kwargs: self._progress(task_id, *args, **kwargs),
                    cancel_check=lambda: self.is_cancelled(task_id),
                    on_ocr_summary=lambda summary: self.finalize_ocr_summary(task_id, summary),
                    pages=pages or None,
                    reindex=reindex,
                )
                self._save_completion(task_id, result, revision_id, (reindex or {}).get("previous_document_id"))
                self._snapshot_revision(task_id, revision_id)
        except IngestionCancelledError:
            self._progress(task_id, None, "cancelled", "Đã hủy nạp tài liệu theo yêu cầu người dùng.", error_message=None)
        except (Exception, SystemExit) as exc:
            self._handle_failure(task_id, exc)
        finally:
            self._cleanup_worker(task_id)

    def _run(self, task_id, file_path, document_type, de_muc_id, domain="lao_dong"):
        from labor_rag.services.ingestion import IngestionCancelledError, IngestionPipeline
        try:
            if self.is_cancelled(task_id):
                raise IngestionCancelledError("Đã hủy nạp tài liệu theo yêu cầu người dùng.")
            with self.runtime.operation():
                pipeline = IngestionPipeline(self.runtime.settings, self.runtime.storage())
                result = pipeline.run(file_path, task_id, document_type, domain=domain, de_muc_id=de_muc_id,
                    progress=lambda *args, **kwargs: self._progress(task_id, *args, **kwargs),
                    cancel_check=lambda: self.is_cancelled(task_id),
                    on_page=lambda page: self.record_ocr_page(task_id, page),
                    on_ocr_summary=lambda summary: self.finalize_ocr_summary(task_id, summary))
                self._save_completion(task_id, result)
        except IngestionCancelledError:
            self._progress(task_id, None, "cancelled", "Đã hủy nạp tài liệu theo yêu cầu người dùng.", error_message=None)
        except (Exception, SystemExit) as exc:
            self._handle_failure(task_id, exc)
        finally:
            self._cleanup_worker(task_id)

    def close(self):
        self.executor.shutdown(wait=True)
