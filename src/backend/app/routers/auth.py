from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.backend.app.models.database import User
from src.backend.app.models.schemas import UserRegister, UserLogin, UserResponse, TokenResponse
from src.backend.app.repositories.postgres import get_db, UserRepository
from src.backend.app.utils.auth import verify_password, get_password_hash, create_access_token
from src.backend.app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse)
def register(req: UserRegister, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    if user_repo.get_by_username(req.username):
        raise HTTPException(status_code=400, detail="Tên người dùng đã tồn tại")
    if user_repo.get_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email đã được đăng ký")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        full_name=req.full_name or req.username,
        role=req.role or "lawyer"
    )
    user = user_repo.create(user)
    token = create_access_token(user.username)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))

@router.post("/login", response_model=TokenResponse)
def login(req: UserLogin, db: Session = Depends(get_db)):
    user_repo = UserRepository(db)
    user = user_repo.get_by_username(req.username)
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không chính xác")

    token = create_access_token(user.username)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

