"""画像 → 推演的注入链路测试。

覆盖三处此前断裂的环节：
1. 六维度新字段能存能取，派生指标随之更新；
2. 推演请求不带画像时，服务端按登录用户自动注入；
3. 画像在推演启动时冻结成快照落库，事后改画像不影响历史推演。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.dependencies import resolve_user_profile
from app.db.session import SessionLocal
from app.engine.profile_summary import build_profile_summary, compute_derived
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _create_profile(client) -> str:
    resp = client.post("/api/profiles", json={})
    assert resp.status_code == 201, resp.text
    return resp.json()["user_id"]


FULL_FIELDS = {
    "age": 34,
    "gender": "男",
    "city": "杭州",
    "education": "master",
    "marital_status": "married",
    "dependents": 2,
    "family_burden": True,
    "occupation": "产品经理",
    "industry": "互联网",
    "years_experience": 10,
    "skills": ["产品设计", "数据分析"],
    "certificates": ["PMP"],
    "career_history": "大厂 10 年，带过 20 人团队",
    "strengths": "抗压、执行力强",
    "weaknesses": "不擅长销售",
    "assets": 500000,
    "monthly_income": 35000,
    "monthly_expense": 20000,
    "liabilities": 200000,
    "income_stability": "stable",
    "insurance": ["社保", "重疾险"],
    "risk_appetite": "balanced",
    "loss_tolerance": 30,
    "decision_style": "analytical",
    "past_failures": "上次开店选址失误",
    "available_time": "parttime",
    "weekly_hours": 20,
    "support_network": "供应链朋友、两位天使投资人",
    "goals": ["副业转正", "财务自由"],
    "constraints": "不能离开杭州",
    "time_horizon": 5,
    "motivation": "想给家人更好的生活",
}


class TestSixDimensionFields:
    """六维度 28 字段的存取与派生指标。"""

    def test_full_update_roundtrip(self, client):
        """所有新字段可写可读。"""
        uid = _create_profile(client)
        resp = client.put(f"/api/profiles/{uid}", json=FULL_FIELDS)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        for key, value in FULL_FIELDS.items():
            assert data[key] == value, f"字段 {key} 未正确回读"

    def test_derived_metrics(self, client):
        """派生指标由原始字段实时推导。"""
        uid = _create_profile(client)
        data = client.put(f"/api/profiles/{uid}", json=FULL_FIELDS).json()
        d = data["derived"]
        assert d["net_worth"] == 300000                 # 50 万 - 20 万
        assert d["monthly_surplus"] == 15000            # 3.5 万 - 2 万
        assert d["debt_ratio"] == 0.4                   # 20 / 50
        assert d["max_affordable_loss"] == 150000       # 50 万 * 30%
        assert d["runway_months"] == 25.0               # 50 万 / 2 万
        assert d["completeness"] > 0.9

    def test_explicit_null_clears_field(self, client):
        """显式提交 null 可清空字段（exclude_unset 语义）。"""
        uid = _create_profile(client)
        client.put(f"/api/profiles/{uid}", json={"city": "杭州"})
        resp = client.put(f"/api/profiles/{uid}", json={"city": None})
        assert resp.status_code == 200
        assert resp.json()["city"] is None

    def test_unsent_field_preserved(self, client):
        """未提交的字段保持原值，不被误清空。"""
        uid = _create_profile(client)
        client.put(f"/api/profiles/{uid}", json={"city": "杭州", "age": 30})
        resp = client.put(f"/api/profiles/{uid}", json={"age": 31})
        assert resp.json()["city"] == "杭州"
        assert resp.json()["age"] == 31

    def test_me_probe_before_and_after(self, client):
        """/profiles/me 未建返回 exists=false，不抛 404。"""
        resp = client.get("/api/profiles/me")
        assert resp.status_code == 200
        assert resp.json()["exists"] is False
        assert resp.json()["profile"] is None

        _create_profile(client)
        resp = client.get("/api/profiles/me")
        assert resp.json()["exists"] is True
        assert resp.json()["profile"]["user_id"]


class TestProfileSummary:
    """画像 → Agent 摘要的渲染（含投入压力段）。"""

    def test_summary_covers_all_dimensions(self):
        profile = dict(FULL_FIELDS)
        profile["derived"] = compute_derived(profile)
        summary = build_profile_summary(profile, {"budget": 300000})

        for marker in ("· 基本：", "· 职业：", "· 财务：", "· 风险：", "· 时间与资源：", "· 目标："):
            assert marker in summary, f"缺少维度 {marker}"
        assert "34 岁" in summary
        assert "硕士" in summary
        assert "可支配资产 50 万元" in summary
        assert "净资产 30 万元" in summary
        assert "零收入可支撑约 25.0 个月" in summary

    def test_pressure_line_links_budget_to_assets(self):
        """投入压力段把 budget 与资产挂钩。"""
        profile = dict(FULL_FIELDS)
        profile["derived"] = compute_derived(profile)
        summary = build_profile_summary(profile, {"budget": 300000})
        assert "本次决策投入 30 万元" in summary
        assert "占其可支配资产的 60.0%" in summary
        # 30 万 > 可承受亏损 15 万 → 必须提示超额
        assert "15 万元" in summary

    def test_empty_profile_returns_empty(self):
        assert build_profile_summary({}, {"budget": 100000}) == ""
        assert build_profile_summary(None) == ""

    def test_no_budget_no_pressure_line(self):
        profile = {"assets": 500000, "derived": compute_derived({"assets": 500000})}
        summary = build_profile_summary(profile, {"city": "杭州"})
        assert "本次决策投入" not in summary


class TestAutoInjection:
    """服务端自动注入：请求不带画像也能拿到登录用户的画像。"""

    def _current_user(self):
        from app.api.dependencies import get_current_user

        override = app.dependency_overrides.get(get_current_user)
        assert override is not None, "测试需要 conftest 的登录用户覆盖"
        return override()

    def test_injects_stored_profile(self, client):
        uid = _create_profile(client)
        client.put(f"/api/profiles/{uid}", json=FULL_FIELDS)

        db = SessionLocal()
        try:
            resolved = resolve_user_profile(None, db, self._current_user())
        finally:
            db.close()
        assert resolved["assets"] == 500000
        assert resolved["derived"]["net_worth"] == 300000

    def test_request_override_wins(self, client):
        """请求体字段覆盖存储值，用于「假如我有两倍资产」的假设推演。"""
        uid = _create_profile(client)
        client.put(f"/api/profiles/{uid}", json=FULL_FIELDS)

        db = SessionLocal()
        try:
            resolved = resolve_user_profile({"assets": 1000000}, db, self._current_user())
        finally:
            db.close()
        assert resolved["assets"] == 1000000
        assert resolved["city"] == "杭州"                      # 未覆盖字段保留
        assert resolved["derived"]["net_worth"] == 800000      # 派生指标同步重算

    def test_no_profile_returns_empty(self, client):
        db = SessionLocal()
        try:
            resolved = resolve_user_profile(None, db, self._current_user())
        finally:
            db.close()
        assert resolved == {}


class TestFrozenSnapshot:
    """推演启动时冻结画像快照，改画像不影响历史推演。"""

    def test_snapshot_written_on_simulation(self, client):
        uid = _create_profile(client)
        client.put(f"/api/profiles/{uid}", json=FULL_FIELDS)

        resp = client.post("/api/simulations", json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 300000, "city": "杭州", "industry": "奶茶", "span_years": 2},
        })
        assert resp.status_code == 200, resp.text
        session_id = resp.json()["session_id"]

        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT user_profile FROM simulation_sessions WHERE id = :sid"),
                {"sid": session_id},
            ).first()
        finally:
            db.close()
        assert row is not None
        assert row[0] is not None and "500000" in row[0], "画像快照未落库"

    def test_snapshot_unaffected_by_later_edit(self, client):
        uid = _create_profile(client)
        client.put(f"/api/profiles/{uid}", json=FULL_FIELDS)
        session_id = client.post("/api/simulations", json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 300000, "city": "杭州", "industry": "奶茶", "span_years": 2},
        }).json()["session_id"]

        # 事后把资产改成 1 元
        client.put(f"/api/profiles/{uid}", json={"assets": 1})

        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT user_profile FROM simulation_sessions WHERE id = :sid"),
                {"sid": session_id},
            ).first()
        finally:
            db.close()
        assert "500000" in row[0], "历史推演的画像快照被后续编辑污染"

    def test_session_detail_returns_the_frozen_profile_snapshot(self, client):
        uid = _create_profile(client)
        client.put(f"/api/profiles/{uid}", json=FULL_FIELDS)
        session_id = client.post("/api/simulations", json={
            "scenario_id": "milktea_startup",
            "decision_vars": {
                "budget": 300000,
                "city": "杭州",
                "industry": "奶茶",
                "span_years": 2,
            },
        }).json()["session_id"]

        detail = client.get(f"/api/sessions/{session_id}")

        assert detail.status_code == 200, detail.text
        assert detail.json()["user_profile"]["weekly_hours"] == 20
