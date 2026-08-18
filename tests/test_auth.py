"""认证端点测试（注册 / 登录 / 当前用户）。

使用独立内存 SQLite，覆盖 get_db 依赖，避免污染业务库。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.api.dependencies import get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False)

    def _override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register(c, username="alice", password="secret123", email=None):
    body = {"username": username, "password": password}
    if email:
        body["email"] = email
    return c.post("/api/auth/register", json=body)


def test_register_success(client):
    r = _register(client)
    assert r.status_code == 201
    data = r.json()
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alice"
    assert data["access_token"]


def test_register_duplicate_username(client):
    _register(client, username="bob")
    r = _register(client, username="bob", password="other456")
    assert r.status_code == 409
    assert r.json()["code"] == "USERNAME_TAKEN"


def test_register_duplicate_email(client):
    _register(client, username="user1", email="same@example.com")
    r = _register(client, username="user2", email="same@example.com")
    assert r.status_code == 409
    assert r.json()["code"] == "EMAIL_TAKEN"


def test_register_short_password(client):
    r = _register(client, username="xuser", password="short")
    assert r.status_code == 422


def test_register_rejects_password_over_bcrypt_byte_limit(client):
    r = _register(client, username="longpassword", password="x" * 73)
    assert r.status_code == 422


def test_register_bad_username(client):
    r = _register(client, username="a", password="secret123")
    assert r.status_code == 422


def test_login_success(client):
    _register(client, username="carol")
    r = client.post(
        "/api/auth/login",
        json={"identifier": "carol", "password": "secret123"},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_login_by_email(client):
    _register(client, username="erin", email="erin@example.com")
    r = client.post(
        "/api/auth/login",
        json={"identifier": "erin@example.com", "password": "secret123"},
    )
    assert r.status_code == 200


def test_login_wrong_password(client):
    _register(client, username="dave")
    r = client.post(
        "/api/auth/login",
        json={"identifier": "dave", "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_CREDENTIALS"


def test_me_requires_token(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401


def test_me_with_token(client):
    reg = _register(client, username="frank").json()
    token = reg["access_token"]
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "frank"


def test_me_invalid_token(client):
    r = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert r.status_code == 401
