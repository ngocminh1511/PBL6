"""One upload worker, with durable task state and no demo fallbacks."""
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import update
from src.backend.app.models.database import IngestionTask, DocumentRecord, FileArtifact

class IngestionService:
    def __init__(self, runtime, database):
        self.runtime, self.database = runtime, database
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="legal-ingestion")

    def recover_interrupted(self):
        if self.database.available:
            with self.database.session() as db:
                db.execute(update(IngestionTask).where(IngestionTask.status.notin_(["completed", "failed"]))
                    .values(status="failed", current_step="Backend đã khởi động lại; cần nạp lại file.",
                            error_message="interrupted_by_restart"))
                db.commit()

    def submit(self, task_id, file_path, document_type, de_muc_id=None):
        # Reserve a config snapshot for both queued and running uploads.
        with self.runtime.lock:
            self.runtime.active += 1
        try:
            self.executor.submit(self._run, task_id, file_path, document_type, de_muc_id)
        except Exception:
            with self.runtime.lock:
                self.runtime.active -= 1
            raise

    def _progress(self, task_id, value, status, step, **fields):
        with self.database.session() as db:
            task = db.get(IngestionTask, task_id)
            if task:
                task.progress, task.status, task.current_step = value, status, step
                for key, val in fields.items():
                    if hasattr(task, key):
                        setattr(task, key, val)
                db.commit()

    def _run(self, task_id, file_path, document_type, de_muc_id):
        from labor_rag.services.ingestion import IngestionPipeline, IngestionInputError
        try:
            with self.runtime.operation():
                pipeline = IngestionPipeline(self.runtime.settings, self.runtime.storage())
                result = pipeline.run(file_path, task_id, document_type, de_muc_id=de_muc_id,
                    progress=lambda *args, **kwargs: self._progress(task_id, *args, **kwargs))
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
                    task.status, task.progress, task.current_step = "completed", 100, "Đã lưu nguồn R2 và lập chỉ mục cloud."
                    task.total_chunks = result["total_chunks"]
                    task.embedded_chunks = result.get("embedded_chunks", result["total_chunks"])
                    db.commit()
        except (Exception, SystemExit) as exc:
            message = str(exc) if isinstance(exc, IngestionInputError) else "Nạp tài liệu chưa hoàn tất (" + type(exc).__name__ + "). Có thể nạp lại để tiếp tục."
            self._progress(task_id, 0, "failed", message, error_message=message)
        finally:
            with self.runtime.lock:
                self.runtime.active -= 1

    def close(self):
        self.executor.shutdown(wait=True)
