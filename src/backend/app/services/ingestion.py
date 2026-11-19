"""One upload worker, with durable task state and no demo fallbacks."""
from concurrent.futures import ThreadPoolExecutor
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
                    cancel_check=lambda: self.is_cancelled(task_id))
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
                        "reused_chunks": result.get("reused_chunks", 0)}
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
