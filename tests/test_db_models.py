"""数据库模型测试（TDD：先写能失败的测试，再补齐实现）。

覆盖：
- init_db() 后 9 张表全部存在
- 每张表 insert -> select -> update -> delete CRUD round-trip（单 session，结束 rollback，不污染数据）

运行：
    python -m pytest tests/test_db_models.py -q
"""

import pytest
from sqlalchemy import inspect

from app.db.models import (
    AgentMemory,
    Asset,
    KbChunk,
    Scenario,
    SimulationEvent,
    SimulationMessage,
    SimulationSession,
    TABLE_NAMES,
    User,
    UserProfile,
)
from app.db.session import SessionLocal, engine, init_db


@pytest.fixture(autouse=True)
def _db_session():
    """每个测试用独立 session；结束 rollback 保证不污染库。"""
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_user(session) -> User:
    user = User(email="seed@example.com", username="seed")
    session.add(user)
    session.flush()
    return user


def _seed_scenario(session, scenario_id: str = "sc_seed") -> Scenario:
    scenario = Scenario(
        scenario_id=scenario_id,
        title="Seed Scenario",
        decision_source={"version": 1},
    )
    session.add(scenario)
    session.flush()
    return scenario


def _crud_roundtrip(session, model, insert_kwargs, update_kwargs):
    obj = model(**insert_kwargs)
    session.add(obj)
    session.flush()
    pk = obj.id
    assert pk is not None

    fetched = session.get(model, pk)
    assert fetched is not None

    for key, value in update_kwargs.items():
        setattr(fetched, key, value)
    session.flush()

    updated = session.get(model, pk)
    for key, value in update_kwargs.items():
        assert getattr(updated, key) == value

    session.delete(updated)
    session.flush()
    assert session.get(model, pk) is None


def test_nine_tables_created():
    init_db()
    existing = set(inspect(engine).get_table_names())
    assert set(TABLE_NAMES).issubset(existing), f"缺少表: {set(TABLE_NAMES) - existing}"


def test_crud_users(_db_session):
    _crud_roundtrip(
        _db_session,
        User,
        {"email": "u1@example.com", "username": "alice"},
        {"username": "alice2"},
    )


def test_crud_scenarios(_db_session):
    _crud_roundtrip(
        _db_session,
        Scenario,
        {
            "scenario_id": "milktea_startup",
            "title": "奶茶店创业",
            "decision_source": {"version": 1, "agents": []},
        },
        {"status": "published", "title": "奶茶店创业(改)"},
    )


def test_crud_assets(_db_session):
    scenario = _seed_scenario(_db_session, "asset_sc")
    _crud_roundtrip(
        _db_session,
        Asset,
        {
            "scenario_id": scenario.id,
            "kind": "avatar",
            "ref_id": "a1",
            "seed": 7,
        },
        {"seed": 42, "file_url": "https://x/y.png"},
    )


def test_crud_kb_chunks(_db_session):
    scenario = _seed_scenario(_db_session, "kb_sc")
    _crud_roundtrip(
        _db_session,
        KbChunk,
        {
            "scenario_id": scenario.id,
            "content": "开店需评估现金流",
            "type": "case",
            "embedding": [0.1, 0.2],
            "tags": {"domain": "创业"},
        },
        {"industry": "food", "city": "上海"},
    )


def test_crud_simulation_sessions(_db_session):
    scenario = _seed_scenario(_db_session, "sess_sc")
    _crud_roundtrip(
        _db_session,
        SimulationSession,
        {
            "scenario_id": scenario.scenario_id,
            "decision_vars": {"budget": 200000},
            "world_state": {"cash_flow": 0},
            "timeline": [],
        },
        {"phase": "completed", "current_year": 3, "score": 80},
    )


def test_crud_simulation_messages(_db_session):
    scenario = _seed_scenario(_db_session, "msg_sc")
    sim = SimulationSession(
        scenario_id=scenario.scenario_id, decision_vars={}
    )
    _db_session.add(sim)
    _db_session.flush()
    _crud_roundtrip(
        _db_session,
        SimulationMessage,
        {"session_id": sim.id, "year": 1, "role": "market", "content": "扩张"},
        {"content": "收缩"},
    )


def test_crud_simulation_events(_db_session):
    scenario = _seed_scenario(_db_session, "evt_sc")
    sim = SimulationSession(
        scenario_id=scenario.scenario_id, decision_vars={}
    )
    _db_session.add(sim)
    _db_session.flush()
    _crud_roundtrip(
        _db_session,
        SimulationEvent,
        {
            "session_id": sim.id,
            "year": 2,
            "agent": "risk",
            "action": "warn",
            "state_diff": {"cash_flow": -10},
            "payload": {"note": "x"},
        },
        {"action": "escalate"},
    )


def test_crud_user_profiles(_db_session):
    user = _seed_user(_db_session)
    _crud_roundtrip(
        _db_session,
        UserProfile,
        {
            "user_id": user.id,
            "age": 30,
            "skills": ["finance"],
            "assets": 100000,
            "risk_appetite": "aggressive",
        },
        {"age": 31, "family_burden": True},
    )


def test_crud_agent_memories(_db_session):
    user = _seed_user(_db_session)
    _crud_roundtrip(
        _db_session,
        AgentMemory,
        {
            "user_id": user.id,
            "agent_id": "market",
            "domain": "创业",
            "key": "risk_tolerance",
            "value": {"level": "high"},
            "weight": 1.0,
        },
        {"weight": 0.8},
    )
