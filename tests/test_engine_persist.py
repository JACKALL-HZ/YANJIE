"""验证 SimulationEngine 的持久化接线（缺口①）。

run() 结束后应把最终 SimulationState 写入 simulation_sessions 表，
且公共返回类型/行为不变（仍返回 SimulationState）。
"""

from sqlalchemy import func, select

from app.db.models import SimulationSession
from app.db.session import SessionLocal, init_db
from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader


def test_engine_run_persists_session():
    init_db()
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)

    db = SessionLocal()
    try:
        before = db.scalar(
            select(func.count())
            .select_from(SimulationSession)
            .where(SimulationSession.scenario_id == source.scenario_id)
        )
        state = engine.run({"budget": 200000, "span_years": 3}, db=db)
        after = db.scalar(
            select(func.count())
            .select_from(SimulationSession)
            .where(SimulationSession.scenario_id == source.scenario_id)
        )
    finally:
        db.close()

    assert state.phase == "paused"
    assert state.pause_reason == "year_decision_required"
    assert after == before + 1
