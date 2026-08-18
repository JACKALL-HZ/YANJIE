"""用户画像 API —— CRUD 管理用户决策画像。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.db.models import User
from app.schemas.profile import ProfileCreateRequest, ProfileUpdateRequest
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("")
def list_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """返回当前登录用户的画像（每用户至多一条）。"""
    return ProfileService(db).list_by_user(current_user.id)


@router.get("/me")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取当前登录用户的画像；未创建时返回 exists=false 而非 404。

    推演页用它做软引导（未建画像不阻断流程）。
    """
    profile = ProfileService(db).get(current_user.id)
    if profile is None:
        return {"exists": False, "profile": None}
    return {"exists": True, "profile": profile}


@router.post("", status_code=201)
def create_profile(
    body: ProfileCreateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """创建当前登录用户的画像（默认值）。归属恒为登录用户，无需请求体。"""
    existing = ProfileService(db).get(current_user.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="profile already exists")
    return ProfileService(db).create(current_user.id)


@router.get("/{user_id}")
def get_profile(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """获取用户画像（仅允许访问自己的画像）。"""
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该画像")
    result = ProfileService(db).get(user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return result


@router.put("/{user_id}")
def update_profile(
    user_id: str,
    body: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """更新用户画像字段（仅允许修改自己的画像）。

    用 `exclude_unset` 而非 `exclude_none`：未提交的字段保持原值，
    显式提交 null 表示「清空该字段」（否则用户填错后永远改不回空）。
    """
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该画像")
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="no fields to update")
    result = ProfileService(db).update(user_id, fields)
    if result is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return result
