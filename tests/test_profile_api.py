"""用户画像 API 测试 —— CRUD + 边界。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _create_profile(client):
    """创建当前登录用户的画像（后端忽略请求体 user_id，以登录用户为准）。"""
    resp = client.post("/api/profiles", json={"user_id": "ignored"})
    assert resp.status_code == 201, f"create failed: {resp.text}"
    return resp.json()


class TestProfileCRUD:
    """画像 CRUD 基本功能（按登录用户隔离）。"""

    def test_create_returns_defaults(self, client):
        """POST 创建画像返回默认值。"""
        data = _create_profile(client)
        assert data["user_id"]  # 当前登录用户 id
        assert data["risk_appetite"] == "balanced"
        assert data["skills"] == []

    def test_create_duplicate_rejected(self, client):
        """重复创建当前用户画像返回 409。"""
        _create_profile(client)
        resp = client.post("/api/profiles", json={"user_id": "ignored"})
        assert resp.status_code == 409

    def test_get_existing(self, client):
        """GET 自己的画像。"""
        uid = _create_profile(client)["user_id"]
        resp = client.get(f"/api/profiles/{uid}")
        assert resp.status_code == 200
        assert resp.json()["user_id"] == uid

    def test_get_other_forbidden(self, client):
        """GET 他人画像返回 403（归属校验）。"""
        resp = client.get("/api/profiles/someone-else")
        assert resp.status_code == 403

    def test_update_fields(self, client):
        """PUT 更新自己的画像字段。"""
        uid = _create_profile(client)["user_id"]
        resp = client.put(f"/api/profiles/{uid}", json={
            "age": 30,
            "risk_appetite": "aggressive",
            "skills": ["marketing", "sales"],
            "assets": 200000,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["age"] == 30
        assert data["risk_appetite"] == "aggressive"
        assert data["skills"] == ["marketing", "sales"]
        assert data["assets"] == 200000

    def test_update_other_forbidden(self, client):
        """PUT 他人画像返回 403。"""
        resp = client.put("/api/profiles/someone-else", json={"age": 25})
        assert resp.status_code == 403

    def test_update_no_fields_rejected(self, client):
        """空 body 返回 422。"""
        uid = _create_profile(client)["user_id"]
        resp = client.put(f"/api/profiles/{uid}", json={})
        assert resp.status_code == 422

    def test_list_profiles(self, client):
        """列出仅含当前登录用户的画像。"""
        _create_profile(client)
        resp = client.get("/api/profiles")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        # 全部属于同一用户
        assert all(it["user_id"] == items[0]["user_id"] for it in items)
