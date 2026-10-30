from datetime import datetime, timedelta
from typing import Optional, Any
import hashlib
import hmac
import json
import base64

from src.backend.app.config import settings

try:
    import bcrypt
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            # Fallback check if it was hashed with standard library fallback
            salt = hashed_password[:16]
            expected = hashed_password[16:]
            actual = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
            return hmac.compare_digest(expected, actual)

    def get_password_hash(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
except Exception:
    # Standard library fallback hash
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            salt = hashed_password[:16]
            expected = hashed_password[16:]
            actual = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
            return hmac.compare_digest(expected, actual)
        except Exception:
            return False

    def get_password_hash(password: str) -> str:
        salt = hashlib.md5(str(datetime.utcnow().timestamp()).encode()).hexdigest()[:16]
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
        return salt + hashed

try:
    from jose import jwt, JWTError
    def create_access_token(subject: str | Any, expires_delta: Optional[timedelta] = None) -> str:
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {"exp": expire, "sub": str(subject)}
        return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def decode_access_token(token: str) -> Optional[str]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
            return payload.get("sub")
        except JWTError:
            return None
except ImportError:
    # Standard HMAC-SHA256 token fallback
    def create_access_token(subject: str | Any, expires_delta: Optional[timedelta] = None) -> str:
        exp = (datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))).timestamp()
        data = json.dumps({"sub": str(subject), "exp": exp})
        b64_data = base64.urlsafe_b64encode(data.encode()).decode()
        sig = hmac.new(settings.JWT_SECRET.encode(), b64_data.encode(), hashlib.sha256).hexdigest()
        return f"{b64_data}.{sig}"

    def decode_access_token(token: str) -> Optional[str]:
        try:
            b64_data, sig = token.split(".")
            expected_sig = hmac.new(settings.JWT_SECRET.encode(), b64_data.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected_sig):
                return None
            data = json.loads(base64.urlsafe_b64decode(b64_data.encode()).decode())
            if datetime.utcnow().timestamp() > data.get("exp", 0):
                return None
            return data.get("sub")
        except Exception:
            return None
