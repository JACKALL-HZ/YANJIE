"""Shared pytest configuration for the backend test suite."""

import os
import uuid

# 测试隔离：强制使用内存 SQLite 与内存 checkpointer，
# 避免 autouse 清空逻辑污染业务库 yanjie_dev.db（符合测试隔离红线）。
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CHECKPOINTER_URL"] = "memory"
os.environ["LLM_USE_STUB"] = "1"
os.environ["PAUSE_EACH_YEAR"] = "0"
# 测试豁免速率限制（RateLimitMiddleware 默认 60/60s，完整测试集会触发 429 连锁失败）
os.environ["RATE_LIMIT_REQUESTS"] = "0"

import pytest
from sqlalchemy import text

from app.api.dependencies import get_current_user, get_optional_user
from app.core.jwt import create_access_token
from app.core.security import hash_password
from app.db.models import User
from app.db.session import SessionLocal, engine, init_db

# 反向依赖顺序清理，避免外键约束（SQLite 默认不强制外键，但按序更稳妥）
_CLEAN_ORDER = [
    "simulation_events",
    "simulation_messages",
    "agent_memories",
    "assets",
    "kb_chunks",
    "simulation_sessions",
    "user_profiles",
    "scenarios",
    "users",
]


@pytest.fixture(autouse=True)
def _clean_db():
    """每个测试前清空 9 张表，避免 engine 自动落库产生的已提交数据污染断言。

    开发期 SQLite 文件库被多个测试共享，run() 的持久化会提交真实数据，
    此处统一在测试前 wipe，保证用例间互不干扰。
    """
    init_db()
    db = SessionLocal()
    try:
        for table in _CLEAN_ORDER:
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(autouse=True)
def _override_current_user(request):
    """非 auth 模块：覆盖 get_current_user 为已登录测试用户，避免写测试 401。

    生产代码已用 Depends(get_current_user) 强制鉴权（无 token → 401，由
    test_auth 模块验证）。其余集成测试假设「已登录」状态，用依赖覆盖注入
    一个内存测试用户（不校验 token），从而无需逐测试注入 Authorization 头。
    client fixture 是函数内/模块级变量还是 fixture 都不影响（覆盖是 app 级）。
    test_auth 模块保留真实鉴权（验证无 token → 401 / 有 token → 200）。
    """
    from app.main import app

    if request.module.__name__ == "test_auth" or request.module.__name__.endswith(".test_auth"):
        yield
        return
    db = SessionLocal()
    try:
        uid = f"test_{uuid.uuid4().hex[:12]}"
        user = User(username=uid, password_hash=hash_password("Test@123456"))
        db.add(user)
        db.commit()
        db.refresh(user)
        snapshot = user
    finally:
        db.close()

    def _fake_current_user():
        return snapshot

    app.dependency_overrides[get_current_user] = _fake_current_user
    app.dependency_overrides[get_optional_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_optional_user, None)
