"""LangGraph Checkpointer 测试 —— 中断恢复、状态查询、兼容性。"""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader
from app.main import app


# ── 引擎级测试 ──


class TestCheckpointerIntegration:
    """Checkpointer 集成：图编译 + 调用 + 中断/恢复。"""

    def test_engine_compiles_and_runs_with_checkpointer(self):
        """挂 checkpointer 的引擎正常完成推演。"""
        source = ScenarioLoader("scenarios").load("milktea_startup")
        engine = SimulationEngine(source, use_stub=True)
        assert engine._checkpointer is not None
        state = engine.run_batch({"budget": 200000, "span_years": 2})
        assert state.phase == "completed"
        assert state.result is not None

    def test_postgres_checkpointer_requires_installed_saver(self):
        source = ScenarioLoader("scenarios").load("milktea_startup")
        from app.core.config import get_settings

        settings = replace(
            get_settings(),
            checkpointer_url="postgresql://demo:demo@localhost/yanjie",
        )

        with pytest.raises(RuntimeError, match="langgraph-checkpoint-postgres"):
            SimulationEngine(source, use_stub=True, settings=settings)

    def test_initial_event_sequence_stops_after_decision_pause(self):
        source = ScenarioLoader("scenarios").load("milktea_startup")
        events = list(
            SimulationEngine(source, use_stub=True).iter_events({"budget": 200000})
        )

        assert [event.event_type.value for event in events] == [
            "simulation.started",
            "simulation.paused",
        ]

    def test_engine_pauses_on_intervention(self):
        """低预算触发关键事件 → 引擎暂停并 yield 干预事件。"""
        source = ScenarioLoader("scenarios").load("milktea_startup")
        engine = SimulationEngine(source, use_stub=True)
        initial = list(engine.iter_events({"budget": 60000}))[-1].state_snapshot
        events = list(
            engine.resume_events(
                initial.session_id, initial, "先压缩非必要投入",
            )
        )
        event_types = [e.event_type.value for e in events]
        assert "intervention.pending" in event_types
        assert "simulation.paused" in event_types

    def test_engine_resume_after_intervention(self):
        """暂停 → 提交选择 → 恢复 → 跑完。"""
        source = ScenarioLoader("scenarios").load("milktea_startup")
        engine = SimulationEngine(source, use_stub=True)
        initial = list(engine.iter_events({"budget": 60000}))[-1].state_snapshot
        events = list(
            engine.resume_events(
                initial.session_id, initial, "先压缩非必要投入",
            )
        )
        # 找到暂停事件，提取必要信息
        paused_events = [
            e for e in events
            if e.event_type.value == "simulation.paused"
        ]
        assert len(paused_events) == 1
        paused = paused_events[0]
        session_id = paused.session_id
        saved_state = paused.state_snapshot
        assert saved_state is not None
        assert saved_state.pending_intervention is not None

        # 恢复
        choice = saved_state.pending_intervention.options[0]
        resume_events = list(engine.resume_events(
            session_id, saved_state, choice,
        ))
        resume_types = [e.event_type.value for e in resume_events]
        assert "year.completed" in resume_types
        final = resume_events[-1].state_snapshot
        assert final.pending_intervention is None
        assert final.pause_reason in {"year_decision_required", "horizon_review"}

    def test_resume_completes_simulation(self):
        """恢复后的推演能达到 completed 状态。"""
        source = ScenarioLoader("scenarios").load("milktea_startup")
        engine = SimulationEngine(source, use_stub=True)
        initial = list(
            engine.iter_events({"budget": 60000, "span_years": 1})
        )[-1].state_snapshot
        events = list(
            engine.resume_events(
                initial.session_id, initial, "先压缩非必要投入",
            )
        )
        paused_events = [
            e for e in events
            if e.event_type.value == "simulation.paused"
        ]
        assert len(paused_events) == 1
        paused = paused_events[0]
        saved_state = paused.state_snapshot
        choice = saved_state.pending_intervention.options[0]

        resume_events = list(engine.resume_events(
            paused.session_id, saved_state, choice,
        ))
        paused = resume_events[-1].state_snapshot
        final = engine.finalize_horizon_review(paused)
        assert final.phase == "completed"

    def test_run_with_intervention_choices_no_pause(self):
        """提前提供干预选择 → 不暂停直接跑完。"""
        source = ScenarioLoader("scenarios").load("milktea_startup")
        engine = SimulationEngine(source, use_stub=True)
        state = engine.run_batch(
            {"budget": 60000},
            intervention_choices={1: "cut_costs"},
        )
        assert state.phase == "completed"
        assert len(state.interventions) >= 1


class TestCheckpointerNoCheckpointer:
    """无 checkpointer（MemorySaver）时的行为：功能完整但无跨进程持久化。"""

    def test_memory_saver_does_not_persist_across_engines(self):
        """MemorySaver 只在引擎生命周期内有效，新引擎从零开始。"""
        source = ScenarioLoader("scenarios").load("milktea_startup")
        engine1 = SimulationEngine(source, use_stub=True)
        state1 = engine1.run_batch({"budget": 200000, "span_years": 2})
        assert state1.phase == "completed"

        # 新引擎不受旧引擎 checkpoint 影响
        engine2 = SimulationEngine(source, use_stub=True)
        state2 = engine2.run_batch({"budget": 200000, "span_years": 2})
        assert state2.phase == "completed"
        assert state2.session_id != state1.session_id


# ── API 级测试 ──


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _create_and_pause(client):
    """创建低预算模拟并完成首年决策，返回干预暂停数据。"""
    resp = client.post("/api/simulations", json={
        "scenario_id": "milktea_startup",
        "decision_vars": {"budget": 60000},
    })
    assert resp.status_code == 200
    initial = resp.json()
    assert initial["pause_reason"] == "year_decision_required"
    resumed = client.post(
        f"/api/simulations/{initial['session_id']}/resume",
        json={"choice": "先压缩非必要投入"},
    )
    assert resumed.status_code == 200
    data = resumed.json()
    if data.get("pending_intervention") is not None:
        return data
    pytest.skip("simulation did not pause (no intervention triggered)")


class TestResumeAPI:
    """POST /api/simulations/{id}/resume 端点。"""

    def test_grad_exam_resume_accepts_localized_intervention_choice(self, client):
        """考研场景提交中文干预选项时，恢复接口不应返回 422。"""
        response = client.post(
            "/api/simulations",
            json={
                "scenario_id": "grad_exam",
                "decision_vars": {
                    "target_school": "清华大学",
                    "current_level": "普通本科",
                    "prep_months": 8,
                    "budget": 10000,
                },
            },
        )
        assert response.status_code == 200
        initial = response.json()
        assert initial["pause_reason"] == "year_decision_required"
        advanced = client.post(
            f"/api/simulations/{initial['session_id']}/resume",
            json={"choice": "制定每日学习计划并开始执行"},
        )
        assert advanced.status_code == 200
        data = advanced.json()
        assert data["pending_intervention"]["options"] == [
            "继续冲刺",
            "边工作边备考",
        ]

        resumed = client.post(
            f"/api/simulations/{data['session_id']}/resume",
            json={"choice": "继续冲刺"},
        )

        assert resumed.status_code == 200
        assert resumed.json()["session_id"] == data["session_id"]

    def test_resume_endpoint_returns_simulation_response(self, client):
        """恢复接口正常返回。"""
        data = _create_and_pause(client)
        session_id = data["session_id"]
        pending = data["pending_intervention"]
        choice = pending["options"][0]

        resp = client.post(f"/api/simulations/{session_id}/resume", json={
            "choice": choice,
        })
        assert resp.status_code == 200
        result = resp.json()
        assert result["session_id"] == session_id
        assert result["phase"] in {"paused", "horizon_review", "completed"}
        assert result["pending_intervention"] is None

    def test_resume_nonexistent_session(self, client):
        """不存在的 session 返回 404。"""
        resp = client.post("/api/simulations/nonexistent-id/resume", json={
            "choice": "A",
        })
        assert resp.status_code == 404

    def test_resume_non_paused_session(self, client):
        """已完成/运行中的 session 拒绝 resume。"""
        resp = client.post("/api/simulations", json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 200000, "span_years": 2},
        })
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]
        completed = client.post(f"/api/simulations/{session_id}/resume", json={
            "choice": "结束推演",
        })
        assert completed.status_code == 200
        assert completed.json()["phase"] == "completed"
        resp2 = client.post(f"/api/simulations/{session_id}/resume", json={
            "choice": "继续推进",
        })
        assert resp2.status_code == 409


class TestStateAPI:
    """GET /api/simulations/{id}/state 端点。"""

    def test_state_endpoint_returns_phase(self, client):
        """查询状态端点返回阶段和年份。"""
        data = _create_and_pause(client)
        session_id = data["session_id"]

        resp = client.get(f"/api/simulations/{session_id}/state")
        assert resp.status_code == 200
        state_data = resp.json()
        assert state_data["session_id"] == session_id
        assert state_data["phase"] == "paused"
        assert state_data["has_pending_intervention"] is True

    def test_state_not_found(self, client):
        """不存在返回 404。"""
        resp = client.get("/api/simulations/nonexistent/state")
        assert resp.status_code == 404
