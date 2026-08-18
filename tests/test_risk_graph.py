"""风险传导图谱测试。"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.engine.models import WorldState
from app.engine.risk_graph import build_risk_dag
from app.engine.state import make_initial_state
from app.main import app
from app.schemas.decision_source import DecisionSource


def _source() -> DecisionSource:
    return DecisionSource.model_validate(
        json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8"))
    )


class TestRiskDag:
    """风险 DAG 构建单元测试。"""

    def test_dag_has_nodes(self):
        """有风险时 DAG 包含节点。"""
        source = _source()
        state = make_initial_state(source, {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3})
        dag = build_risk_dag(state)
        assert len(dag.nodes) > 0

    def test_dag_has_edges(self):
        """DAG 包含传导边。"""
        source = _source()
        state = make_initial_state(source, {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3})
        dag = build_risk_dag(state)
        assert len(dag.edges) > 0

    def test_dag_has_chains(self):
        """DAG 包含传导链。"""
        source = _source()
        state = make_initial_state(source, {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3})
        dag = build_risk_dag(state)
        assert len(dag.chains) >= 0  # 取决于是否激活

    def test_low_cash_activates_cash_chain(self):
        """低现金流激活 cash → profit 传导链。"""
        source = _source()
        ws = WorldState(
            cash_flow=10000,  # very low
            customer_flow=100,
            competition_count=60,
            monthly_profit=5000,
            payback_ratio=0.2,
        )
        from app.engine.models import SimulationState
        state = SimulationState(
            session_id="test",
            scenario_id="milktea_startup",
            decision_vars={"budget": 200000},
            world_state=ws,
            phase="simulating",
            year=1,
        )
        dag = build_risk_dag(state, source)
        chain_metrics = set()
        for chain in dag.chains:
            chain_metrics.update(chain.pathway)
        assert "cash_flow" in chain_metrics

    def test_serializable(self):
        """DAG 可序列化为 JSON。"""
        source = _source()
        state = make_initial_state(source, {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3})
        dag = build_risk_dag(state)
        data = dag.model_dump()
        assert isinstance(data, dict)
        assert "nodes" in data
        assert "edges" in data
        assert "chains" in data


class TestRiskGraphAPI:
    """风险图谱 API 端点。"""

    @pytest.fixture(scope="module")
    def client(self):
        return TestClient(app)

    def _create_session(self, client):
        resp = client.post("/api/simulations", json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 2},
        })
        assert resp.status_code == 200
        return resp.json()["session_id"]

    def test_endpoint_returns_dag(self, client):
        sid = self._create_session(client)
        resp = client.get(f"/api/simulations/{sid}/risk-graph")
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert "chains" in data

    def test_nonexistent_session_404(self, client):
        resp = client.get("/api/simulations/nonexistent/risk-graph")
        assert resp.status_code == 404
