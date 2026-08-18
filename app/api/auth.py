"""认证路由 —— 注册 / 登录 / 当前用户（JWT 无状态）。

统一错误码：
- 409 USERNAME_TAKEN / EMAIL_TAKEN：标识已存在
- 401 INVALID_CREDENTIALS：凭证错误
- 422 INVALID_REQUEST：字段校验失败
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.jwt import create_access_token
from app.core.security import hash_password, password_fits_bcrypt_limit, verify_password
from app.db.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: str | None = None
    password: str

    @field_validator("username")
    @classmethod
    def _v_username(cls, v: str) -> str:
        v = v.strip()
        if not (3 <= len(v) <= 32):
            raise ValueError("用户名需 3-32 个字符")
        if not v.replace("_", "").isalnum():
            raise ValueError("用户名仅支持字母、数字、下划线")
        return v

    @field_validator("password")
    @classmethod
    def _v_password(cls, v: str) -> str:
        if not (8 <= len(v) <= 128):
            raise ValueError("密码需 8-128 个字符")
        return v

    @field_validator("password")
    @classmethod
    def _v_password_bytes(cls, v: str) -> str:
        if not password_fits_bcrypt_limit(v):
            raise ValueError("password exceeds bcrypt byte limit")
        return v

    @field_validator("email")
    @classmethod
    def _v_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if "@" not in v or len(v) > 255:
            raise ValueError("邮箱格式不正确")
        return v


class LoginRequest(BaseModel):
    identifier: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    email: str | None
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username or "",
            email=user.email,
            created_at=user.created_at.isoformat() if user.created_at else "",
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


def _token(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, user.username or ""),
        user=UserOut.from_user(user),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = (
        db.execute(
            select(User).where(
                or_(User.username == body.username, User.email == body.email)
            )
        )
        .scalars()
        .first()
    )
    if existing is not None:
        if existing.username == body.username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "USERNAME_TAKEN", "message": "该用户名已被注册"},
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_TAKEN", "message": "该邮箱已被注册"},
        )
    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _token(user)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = (
        db.execute(
            select(User).where(
                or_(
                    User.username == body.identifier,
                    User.email == body.identifier,
                )
            )
        )
        .scalars()
        .first()
    )
    if (
        user is None
        or not user.password_hash
        or not verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "用户名或密码错误"},
        )
    return _token(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_user(current_user)
