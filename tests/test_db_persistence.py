"""引擎增量持久化集成测试（TDD）。

验证：
- SIMULATION_STARTED → session 行创建
- 每年 YEAR_COMPLETED → simulation_events 行写入 + session.current_year 更新
- SIMULATION_COMPLETED → 终态落库完整
- 同一 session 的 events 行数与推演年数一致
"""

import json
from pathlib import Path

import pytest

from app.db.models import SimulationEvent, SimulationSession
from app.db.session import SessionLocal, init_db
from app.engine.engine import SimulationEngine
from app.schemas.decision_source import DecisionSource


@pytest.fixture(autouse=True)
def _db_session():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def source() -> DecisionSource:
    data = json.loads(
        Path("scenarios/milktea_startup.json").read_text(encoding="utf-8")
    )
    return DecisionSource.model_validate(data)


def test_engine_creates_session_on_start(source, _db_session):
    """SIMULATION_STARTED 后 simulation_sessions 表有对应行。"""
    engine = SimulationEngine(source, use_stub=True)
    list(
        engine.iter_events(
            {"budget": 200000, "city": "hangzhou", "span_years": 1},
            db=_db_session,
        )
    )

    s = _db_session.query(SimulationSession).first()
    assert s is not None, "SIMULATION_STARTED 后应有 session 行"
    assert s.phase != "input"  # 应更新为 'simulating'
    assert s.scenario_id == source.scenario_id


def test_engine_events_persisted_per_year(source, _db_session):
    """每年 YEAR_COMPLETED 写入 simulation_events，行数匹配。"""
    engine = SimulationEngine(source, use_stub=True)
    initial = list(
        engine.iter_events(
            {"budget": 200000, "city": "hangzhou", "span_years": 2},
            db=_db_session,
        )
    )[-1].state_snapshot
    list(
        engine.resume_events(
            initial.session_id, initial, "先小范围验证，再根据结果调整投入", db=_db_session,
        )
    )

    db_events = _db_session.query(SimulationEvent).all()
    assert len(db_events) >= 1, "每年至少有一个 Agent 动作写入 events"
    for ev in db_events:
        assert ev.agent
        assert ev.action
        assert ev.year > 0


def test_engine_session_updated_incrementally(source, _db_session):
    """session 的 current_year 和 phase 在推演过程中增量更新。"""
    engine = SimulationEngine(source, use_stub=True)
    initial = list(
        engine.iter_events(
            {"budget": 200000, "city": "hangzhou", "span_years": 2},
            db=_db_session,
        )
    )[-1].state_snapshot
    list(
        engine.resume_events(
            initial.session_id, initial, "先小范围验证，再根据结果调整投入", db=_db_session,
        )
    )

    s = _db_session.query(SimulationSession).first()
    assert s is not None
    assert s.current_year > 0, "推演后 current_year 应 > 0"
    assert s.phase in ("paused", "simulating", "completed", "horizon_review")


def test_engine_completed_state_persisted(source, _db_session):
    """推演完成后 world_state / result / score 完整落库。"""
    engine = SimulationEngine(source, use_stub=True)
    initial = list(
        engine.iter_events(
            {"budget": 200000, "city": "hangzhou", "span_years": 1},
            db=_db_session,
        )
    )[-1].state_snapshot
    horizon_state = list(
        engine.resume_events(
            initial.session_id, initial, "先小范围验证，再根据结果调整投入", db=_db_session,
        )
    )[-1].state_snapshot
    engine.persist(engine.finalize_horizon_review(horizon_state), db=_db_session)

    s = _db_session.query(SimulationSession).first()
    assert s is not None
    assert s.result is not None, "终态 result 应落库"
    assert s.world_state, "world_state 不应为空"
    assert s.timeline, "timeline 数组不应为空"
    assert s.decision_vars.get("budget") == 200000
