"""Demo access is explicit; public appendix routes do not use these dependencies."""
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from types import SimpleNamespace
from src.backend.app.models.database import User
from src.backend.app.repositories.postgres import get_db, UserRepository
from src.backend.app.utils.auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> User:
    repo = UserRepository(db)
    if not token and request.app.state.runtime.settings.DEMO_MODE:
        user = repo.get_by_username("lawyer_demo")
        if not user:
            user = User(username="lawyer_demo", email="demo@lexgraph.local", hashed_password="disabled",
                        full_name="Người dùng demo", role="lawyer")
            db.add(user)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                user = repo.get_by_username("lawyer_demo")
            db.refresh(user)
        return user
    username = decode_access_token(token, config=request.app.state.runtime.settings) if token else None
    user = repo.get_by_username(username) if username else None
    if not user or not user.is_active:
        raise HTTPException(401, "Cần token đăng nhập hợp lệ.", headers={"WWW-Authenticate": "Bearer"})
    return user


def get_current_admin(request: Request, token: str | None = Depends(oauth2_scheme)):
    if request.app.state.runtime.settings.DEMO_MODE:
        return SimpleNamespace(id=None, username="demo", role="admin")
    with request.app.state.database.session() as db:
        user = get_current_user(request=request, token=token, db=db)
        if user.role != "admin":
            raise HTTPException(403, "Cần quyền quản trị.")
        return user
