"""Password compatibility and JWT helpers; demo tokens use a process-local key."""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException
from src.backend.app.config import settings

_DEMO_SIGNING_KEY = secrets.token_urlsafe(48)

def signing_key(config):
    if config.JWT_SECRET:
        return config.JWT_SECRET
    if config.DEMO_MODE:
        return _DEMO_SIGNING_KEY
    raise HTTPException(503, "Cần cấu hình JWT_SECRET.")

def get_password_hash(password):
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(422, "Mật khẩu tối đa 72 byte UTF-8.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    if hashed.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode())
        except ValueError:
            return False
    # Preserve pre-merge accounts created by the old standard-library fallback.
    if len(hashed) == 80:
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), hashed[:16].encode(), 100000).hex()
        return hmac.compare_digest(hashed[16:], actual)
    return False

def create_access_token(subject, expires_delta=None, *, config=None):
    config = config or settings
    expires = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    return jwt.encode({"sub": str(subject), "exp": expires}, signing_key(config), algorithm=config.JWT_ALGORITHM)

def decode_access_token(token, *, config=None):
    config = config or settings
    try:
        return jwt.decode(token, signing_key(config), algorithms=[config.JWT_ALGORITHM]).get("sub")
    except JWTError:
        return None
