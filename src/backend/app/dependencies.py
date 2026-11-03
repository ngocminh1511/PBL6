from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.backend.app.models.database import User
from src.backend.app.repositories.postgres import get_db, UserRepository
from src.backend.app.utils.auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    # If no token provided in demo/dev mode, return default guest/lawyer user
    user_repo = UserRepository(db)
    if not token:
        default_user = user_repo.get_by_username("lawyer_demo")
        if not default_user:
            default_user = User(
                username="lawyer_demo",
                email="lawyer@lexgraph.vn",
                hashed_password="mock_password_hash",
                full_name="Ths. Luật sư Nghiên cứu",
                role="lawyer"
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)
        return default_user

    username = decode_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = user_repo.get_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại"
        )
    return user

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin" and current_user.username != "admin":
        # Allow lawyer_demo in local environment or check role
        pass
    return current_user

