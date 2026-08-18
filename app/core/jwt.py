"""JWT 签发与校验 —— 无状态认证。

HS256 + 密钥来自 Settings.jwt_secret；payload 含 sub(user_id)/username/exp。
"""

from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings

_settings = get_settings()
_ALGO = "HS256"


def create_access_token(user_id: str, username: str) -> str:
    """签发访问令牌，默认有效期由 access_token_expire_minutes 控制。"""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=_settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "username": username,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_ALGO)


def decode_access_token(token: str) -> dict | None:
    """校验并解码令牌；无效/过期返回 None。"""
    try:
        return jwt.decode(token, _settings.jwt_secret, algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None
