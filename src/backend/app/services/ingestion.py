"""One upload worker, with durable task state and no demo fallbacks."""
from concurrent.futures import ThreadPoolExecutor
import json
import threading
from sqlalchemy import update
from src.backend.app.models.database import IngestionTask, DocumentRecord, FileArtifact

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
                db.execute(update(IngestionTask).where(IngestionTask.status.notin_(["completed", "failed", "cancelled"]))
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
            if task.status == "pending":
                task.status = "cancelled"
                task.current_step = "Đã hủy nạp tài liệu theo yêu cầu người dùng."
            else:
                task.current_step = "Đang hủy tiến trình theo yêu cầu..."
            db.commit()
            db.refresh(task)
            return task

    def submit(self, task_id, file_path, document_type, de_muc_id=None, domain="lao_dong"):
        # Reserve a config snapshot for both queued and running uploads.
        with self._cancel_lock:
            self._cancel_events[task_id] = threading.Event()
        with self.runtime.lock:
            self.runtime.active += 1
        try:
            self.executor.submit(self._run, task_id, file_path, document_type, de_muc_id, domain)
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
        pages_file = self.runtime.settings.INTERIM_DIR / "ingestion" / task_id / "ocr_pages.jsonl"
        if not pages_file.exists():
            return None
        entries = [json.loads(line) for line in pages_file.read_text(encoding="utf-8").splitlines() if line.strip()]
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

    def get_ocr_page_text(self, task_id: str, page_number: int) -> dict | None:
        pages_file = self.runtime.settings.INTERIM_DIR / "ingestion" / task_id / "ocr_pages.jsonl"
        if not pages_file.exists():
            return None
        for line in pages_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if int(entry.get("page_number") or 0) == page_number:
                return {
                    "page_number": page_number,
                    "method": str(entry.get("method") or "unknown"),
                    "confidence": entry.get("confidence"),
                    "char_count": int(entry.get("char_count") or 0),
                    "text": str(entry.get("text") or ""),
                }
        return None

    def _run(self, task_id, file_path, document_type, de_muc_id, domain="lao_dong"):
        from labor_rag.services.ingestion import IngestionCancelledError, IngestionPipeline
        from src.backend.app.services.corpus import Corpus
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
                with self.database.session() as db:
                    for record in result["documents"]:
                        existing = db.get(DocumentRecord, record["id"])
                        if existing:
                            for key, value in record.items():
                                setattr(existing, key, value)
                        else:
                            db.add(DocumentRecord(**record))
                    for artifact in result["artifacts"]:
                        row = db.get(FileArtifact, artifact["artifact_id"])
                        if row:
                            row.record = artifact
                        else:
                            db.add(FileArtifact(id=artifact["artifact_id"], record=artifact))
                    task = db.get(IngestionTask, task_id)
                    task.result = {"document_ids": result["document_ids"],
                        "artifact_ids": [a["artifact_id"] for a in result["artifacts"]],
                        "warnings": result["warnings"], "config_version": self.runtime.version,
                        "reused_chunks": result.get("reused_chunks", 0),
                        "ocr_summary": result.get("ocr_summary")}
                    task.document_id = result["document_ids"][0] if len(result["document_ids"]) == 1 else None
                    task.status, task.progress, task.current_step = "completed", 100, "Hoàn tất! Văn bản đã sẵn sàng để xem và tra cứu."
                    task.total_chunks = result["total_chunks"]
                    task.embedded_chunks = result.get("embedded_chunks", result["total_chunks"])
                    db.commit()
                Corpus.cache_clear()
        except IngestionCancelledError:
            self._progress(task_id, None, "cancelled", "Đã hủy nạp tài liệu theo yêu cầu người dùng.", error_message=None)
        except (Exception, SystemExit) as exc:
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
        finally:
            with self._cancel_lock:
                self._cancel_events.pop(task_id, None)
            with self.runtime.lock:
                self.runtime.active -= 1

    def close(self):
        self.executor.shutdown(wait=True)
