"""FastAPI 依赖注入 —— 按请求生命周期提供 DB session / Service / Config。

所有 API 端点通过 Depends(get_xxx) 获取依赖，不直接构造服务对象。
"""

from collections.abc import Generator
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.jwt import decode_access_token
from app.db.models import User
from app.db.repository import ScenarioRepo
from app.db.session import SessionLocal, init_db
from app.scenarios.loader import ScenarioLoader
from app.services.scenario_service import ScenarioService
from app.services.simulation_service import SimulationService


# ── 数据库 ──


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: 按请求生命周期管理 DB session。"""
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── 配置 ──


def get_scenario_loader(
    settings: Settings = Depends(get_settings),
) -> ScenarioLoader:
    return ScenarioLoader(settings.scenario_dir)


# ── 业务服务 ──


def get_scenario_service(
    loader: ScenarioLoader = Depends(get_scenario_loader),
) -> ScenarioService:
    return ScenarioService(loader)


def get_scenario_service_with_db(
    loader: ScenarioLoader = Depends(get_scenario_loader),
    db: Session = Depends(get_db),
) -> ScenarioService:
    """含 DB 回源的场景服务（DB 优先 → 文件系统兜底）。"""
    return ScenarioService(loader, repo=ScenarioRepo(db))


def get_simulation_service(
    settings: Settings = Depends(get_settings),
) -> SimulationService:
    return SimulationService(settings)


# ── 认证 ──


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """从 Authorization: Bearer <jwt> 解出当前登录用户；失败抛 401。"""
    cred_exc = HTTPException(
        status_code=401,
        detail={"code": "UNAUTHORIZED", "message": "无效或过期的登录凭证"},
    )
    if not authorization or not authorization.startswith("Bearer "):
        raise cred_exc
    token = authorization[len("Bearer "):].strip()
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise cred_exc
    user = db.get(User, payload["sub"])
    if user is None:
        raise cred_exc
    return user


def get_optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    """从 Authorization: Bearer <jwt> 解出当前登录用户；无 token 返回 None。

    用于推演/追问等不强制登录的端点 —— 已登录用户享受画像个性化，
    未登录用户仍可正常使用推演功能。
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[len("Bearer "):].strip()
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        return None
    return db.get(User, payload["sub"])


@dataclass(frozen=True)
class RequestActor:
    user: User | None
    anonymous_key: str | None

    @property
    def user_id(self) -> str | None:
        return self.user.id if self.user is not None else None


def get_request_actor(
    current_user: User = Depends(get_current_user),
) -> RequestActor:
    return RequestActor(user=current_user, anonymous_key=None)


def resolve_user_profile(
    request_profile: dict | None,
    db: Session,
    current_user: User | None,
) -> dict:
    """解析本次推演生效的用户画像。

    服务端存储的画像为基底（客户端无法伪造真实身家），
    请求体中显式传入的字段作为「本次推演的临时覆盖」叠加其上，
    便于同一用户做"如果我资产多一倍会怎样"这类假设推演。

    未登录或未建画像时返回 {} —— 推演照常进行，只是少一层个性化，不阻断用户。
    """
    if current_user is None:
        return dict(request_profile or {})

    from app.engine.profile_summary import compute_derived
    from app.services.profile_service import ProfileService

    base = ProfileService(db).get_for_simulation(current_user.id)
    if not request_profile:
        return base
    if not base:
        return dict(request_profile)

    merged = {**base, **{k: v for k, v in request_profile.items() if v is not None}}
    merged["derived"] = compute_derived(merged)
    return merged


def assert_session_owner(
    session_id: str,
    db: Session,
    actor: RequestActor,
) -> "SimulationSession":
    """校验会话存在且归属于当前用户。

    - 不存在 → 404
    - current_user 为 None（未登录）→ 放行
    - 属于其他用户 → 403
    - user_id 为空（历史遗留数据）→ 放行（向后兼容）
    """
    from app.db.models import SimulationSession
    from app.db.repository import SimulationRepo

    session = SimulationRepo(db).get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    # 历史遗留数据：未绑定任何归属标识（早期匿名推演），视为公开可访问，向后兼容。
    if session.user_id is None and session.owner_key is None:
        return session
    if session.user_id == actor.user_id and actor.user_id is not None:
        return session
    if session.owner_key == actor.anonymous_key and actor.anonymous_key is not None:
        return session
    raise HTTPException(status_code=404, detail="session not found")
