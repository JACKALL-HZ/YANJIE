"""安全相关配置 —— CORS / Trusted Hosts / 速率限制占位。

当前 MVP 阶段仅包含 CORS 辅助函数，后续可扩展 JWT 验证、CSRF 等。
"""

import os


def get_allowed_origins() -> list[str]:
    """从环境变量 ALLOWED_ORIGINS 解析允许的源列表。

    返回 ["*"] 表示允许所有源（开发期）。
    生产期应设置具体的逗号分隔域名列表。
    """
    raw = os.getenv("ALLOWED_ORIGINS", "*")
    return [o.strip() for o in raw.split(",") if o.strip()]


# ── 密码哈希 ──

import bcrypt

# bcrypt 仅取明文前 72 字节；超出部分截断，verify 同样截断保持一致。
MAX_PASSWORD_BYTES = 72


def password_fits_bcrypt_limit(password: str) -> bool:
    return len(password.encode("utf-8")) <= MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    """对明文密码做 bcrypt 哈希（返回标准 $2b$... 串）。"""
    if not password_fits_bcrypt_limit(password):
        raise ValueError("password exceeds bcrypt byte limit")
    pw = password.encode("utf-8")
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配；异常视为不匹配。"""
    try:
        if not password_fits_bcrypt_limit(password):
            return False
        pw = password.encode("utf-8")
        return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
