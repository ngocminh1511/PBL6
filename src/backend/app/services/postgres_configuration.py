"""PostgreSQL bootstrap settings can be saved before any application DB exists."""
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter

from dotenv import dotenv_values, set_key
from fastapi import HTTPException
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from .configuration import failure_message


class PostgresConfiguration:
    def __init__(self, runtime, env_file):
        self.runtime = runtime
        self.env_file = Path(env_file)
        self.lock = Lock()

    def stored_url(self):
        try:
            return dotenv_values(self.env_file).get("DATABASE_URL") or ""
        except (OSError, UnicodeError):
            raise HTTPException(503, "Không đọc được file cấu hình khởi động trên backend.") from None

    @staticmethod
    def parse(value):
        try:
            url = make_url(value.strip())
            if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg2"}:
                raise ValueError("unsupported driver")
            if not url.host or not url.database or not url.username:
                raise ValueError("missing fields")
            if url.query.get("sslmode", "require") not in {"require", "verify-full", "verify-ca", "prefer", "allow", "disable"}:
                raise ValueError("invalid SSL mode")
            if url.port is not None and not 1 <= url.port <= 65535:
                raise ValueError("invalid port")
            return url.set(drivername="postgresql")
        except (ValueError, TypeError, ArgumentError):
            raise HTTPException(422, "Chuỗi kết nối PostgreSQL chưa hợp lệ; kiểm tra host, database, tài khoản và SSL.") from None

    def current_url(self):
        return self.stored_url() or self.runtime.base.DATABASE_URL

    @staticmethod
    def same_url(first, second):
        if not first or not second:
            return first == second
        from src.backend.app.repositories.postgres import normalize_database_url
        try:
            return normalize_database_url(first) == normalize_database_url(second)
        except (ValueError, ArgumentError):
            return False

    def config(self, *, saved=False, message=""):
        stored = self.stored_url()
        value = stored or self.runtime.base.DATABASE_URL
        url = None
        if value:
            try:
                url = self.parse(value)
            except HTTPException:
                pass
        override = os.environ.get("DATABASE_URL", "")
        overridden = bool(override)
        with self.runtime.lock:
            available = self.runtime.database.available
            active_url = self.runtime.database.url
        can_apply = bool(stored) and (not available or self.same_url(stored, active_url)) and (
            not override or self.same_url(stored, override))
        pending = bool(stored) and (not available or not self.same_url(stored, active_url))
        return {"configured": bool(value), "connection_status": "connected" if available else "unavailable",
                "host": url.host if url else "", "port": (url.port or 5432) if url else 5432,
                "database": url.database if url else "", "username": url.username if url else "",
                "sslmode": url.query.get("sslmode", "require") if url else "require",
                "password_configured": bool(url and url.password), "environment_override": overridden,
                "source": "environment" if overridden or (not stored and self.runtime.base.DATABASE_URL) else "env_file" if stored else "default",
                "pending_restart": pending and not can_apply, "pending_apply": pending,
                "can_apply": can_apply, "saved": bool(stored), "message": message}

    def candidate(self, body):
        if body.mode == "url":
            value = body.url.strip() if body.url else self.current_url()
            if not value:
                raise HTTPException(422, "Nhập chuỗi kết nối PostgreSQL.")
            url = self.parse(value)
        else:
            if not body.host.strip() or not body.database.strip() or not body.username.strip():
                raise HTTPException(422, "Điền host, tên database và tên người dùng.")
            password = body.password
            if password is None:
                previous = self.current_url()
                try:
                    old = self.parse(previous) if previous else None
                except HTTPException:
                    old = None
                # A blank password preserves it only for the same server/account.
                password = old.password if old and (old.host, old.port or 5432, old.username) == (
                    body.host.strip(), body.port, body.username.strip()) else ""
            url = URL.create("postgresql", username=body.username.strip(), password=password,
                host=body.host.strip(), port=body.port, database=body.database.strip(), query={"sslmode": body.sslmode})
            url = self.parse(url.render_as_string(hide_password=False))
        if "sslmode" not in url.query:
            url = url.update_query_dict({"sslmode": body.sslmode})
        return url.render_as_string(hide_password=False)

    @staticmethod
    def _probe(value):
        from sqlalchemy import create_engine, text
        from src.backend.app.repositories.postgres import normalize_database_url
        engine = create_engine(normalize_database_url(value), connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"},
                               pool_pre_ping=False, hide_parameters=True)
        try:
            with engine.connect() as connection:
                if connection.execute(text("SELECT 1")).scalar_one() != 1:
                    raise RuntimeError("PostgreSQL did not confirm readiness")
        finally:
            engine.dispose()

    def _check(self, value):
        start = perf_counter()
        try:
            self._probe(value)
            result = {"status": "passed", "message": "Kết nối PostgreSQL thành công.", "details": {}}
        except Exception as exc:
            code, message = failure_message(exc)
            if isinstance(exc, ImportError):
                code, message = "dependency", "Backend thiếu driver PostgreSQL; cần cài các thư viện trong extra api."
            elif code == "unavailable":
                message = "Chưa kết nối được PostgreSQL; kiểm tra host, port, SSL và trạng thái dịch vụ."
            elif code == "not_found":
                message = "Không tìm thấy tài nguyên PostgreSQL được yêu cầu."
            pgcode = getattr(getattr(exc, "orig", None), "pgcode", None)
            if pgcode in {"28P01", "28000"}:
                code, message = "authentication", "Tài khoản hoặc mật khẩu PostgreSQL không hợp lệ."
            elif pgcode == "3D000":
                code, message = "not_found", "Không tìm thấy database đã nhập."
            result = {"status": "failed", "message": message, "details": {"error": code}}
        result.update(checked_at=datetime.now(timezone.utc).isoformat(), latency_ms=round((perf_counter() - start) * 1000))
        return result

    def check(self, body):
        return self._check(self.candidate(body))

    def save(self, body):
        if not self.lock.acquire(blocking=False):
            raise HTTPException(409, "Đang lưu kết nối PostgreSQL; thử lại sau.")
        try:
            value = self.candidate(body)
            checked = self._check(value)
            if checked["status"] != "passed":
                raise HTTPException(503, checked["message"])
            # Do not mutate os.environ or any live clients. This is a startup setting.
            try:
                self.env_file.parent.mkdir(parents=True, exist_ok=True)
                result = set_key(str(self.env_file), "DATABASE_URL", value, quote_mode="always", encoding="utf-8")
                if not result[0]:
                    raise OSError("could not persist bootstrap configuration")
            except (OSError, UnicodeError):
                raise HTTPException(503, "Không lưu được DATABASE_URL vào file .env của backend.") from None
            return self.config(saved=True, message="Đã lưu kết nối vào .env. Thông tin vẫn được giữ khi tải lại trang.")
        finally:
            self.lock.release()

    @staticmethod
    def _database(value):
        from src.backend.app.repositories.postgres import Database
        return Database(value)

    def apply(self):
        """Initialize/reconnect a saved DB; changing a live DB requires a restart."""
        if not self.lock.acquire(blocking=False):
            raise HTTPException(409, "Đang cập nhật kết nối PostgreSQL; thử lại sau.")
        runtime = self.runtime
        locked = False
        candidate = staged = None
        try:
            locked = runtime.lock.acquire(blocking=False)
            if not locked or runtime.active:
                raise HTTPException(409, "Có tác vụ đang chạy; đợi hoàn tất rồi áp dụng kết nối.")
            value = self.stored_url()
            if not value:
                raise HTTPException(422, "Chưa có kết nối đã lưu. Nhập thông tin và lưu trước.")
            value = self.parse(value).render_as_string(hide_password=False)
            override = os.environ.get("DATABASE_URL", "")
            if override and not self.same_url(value, override):
                raise HTTPException(409, "DATABASE_URL của tiến trình khác giá trị đã lưu; cập nhật môi trường và khởi động lại backend.")
            if runtime.database.available and not self.same_url(value, runtime.database.url):
                raise HTTPException(409, "Đổi sang database khác đang sử dụng cần khởi động lại backend; kết nối cũ vẫn được giữ.")
            checked = self._check(value)
            if checked["status"] != "passed":
                raise HTTPException(503, checked["message"])
            candidate = self._database(value)
            candidate.start()
            if not candidate.available:
                raise HTTPException(503, "Chưa chuẩn bị được database ứng dụng; kiểm tra quyền tạo bảng và kết nối PostgreSQL.")
            from .runtime import Runtime
            base = runtime.base.model_copy(update={"DATABASE_URL": value})
            staged = Runtime(base, candidate, runtime.catalog, storage_factory=runtime.storage_factory,
                             retrieval_factory=runtime.retrieval_factory)
            staged.load_config()
            staged.ensure_ready()
            runtime.close_resources()
            runtime.database.adopt(candidate)
            runtime.base, runtime.settings = base, staged.settings
            runtime.overrides, runtime.version = staged.overrides, staged.version
            runtime.llm_profiles, runtime.active_llm_profile_id = staged.llm_profiles, staged.active_llm_profile_id
            runtime.collection_models, runtime.configuration_error = staged.collection_models, None
            return self.config(message="Đã áp dụng kết nối PostgreSQL. Bạn có thể lưu các cấu hình hệ thống ngay.")
        finally:
            if staged is not None:
                staged.close_resources(shutdown=True)
            if candidate is not None:
                candidate.close()
            if locked:
                runtime.lock.release()
            self.lock.release()
