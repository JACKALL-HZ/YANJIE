"""Repository 层测试（TDD）。

覆盖：
- SimulationRepo: create/update/get/list_by_scenario
- EventRepo: save/save_batch/get_by_session
- ScenarioRepo: upsert/get
- AgentMemoryRepo: save/get/delete_by_domain
"""

import pytest

from app.db.models import (
    AgentMemory,
    Scenario,
    SimulationEvent,
    SimulationSession,
    User,
)
from app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db_session():
    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_scenario(session, scenario_id: str = "repo_test_sc"):
    s = Scenario(
        scenario_id=scenario_id,
        title="Repo Test",
        decision_source={"version": 1},
    )
    session.add(s)
    session.flush()
    return s


def _seed_user(session, email="r@t.com"):
    u = User(email=email, username="rtest")
    session.add(u)
    session.flush()
    return u


# ── SimulationRepo ──────────────────────────────────────────


def test_simulation_repo_create_and_get(_db_session):
    from app.db.repository import SimulationRepo

    _seed_scenario(_db_session)
    repo = SimulationRepo(_db_session)

    sid = repo.create(
        session_id="sim-001",
        scenario_id="repo_test_sc",
        decision_vars={"budget": 100000},
        world_state={"cash_flow": 100000},
    )
    assert sid is not None

    row = repo.get("sim-001")
    assert row is not None
    assert row.decision_vars == {"budget": 100000}
    assert row.current_year == 0
    assert row.phase == "simulating"


def test_simulation_repo_update(_db_session):
    from app.db.repository import SimulationRepo

    _seed_scenario(_db_session)
    repo = SimulationRepo(_db_session)
    repo.create(
        session_id="sim-002",
        scenario_id="repo_test_sc",
        decision_vars={},
        world_state={},
    )

    repo.update("sim-002", current_year=3, phase="completed", score=85)
    row = repo.get("sim-002")
    assert row.current_year == 3
    assert row.phase == "completed"
    assert row.score == 85


def test_simulation_repo_get_nonexistent(_db_session):
    from app.db.repository import SimulationRepo

    repo = SimulationRepo(_db_session)
    assert repo.get("nonexistent-id") is None


def test_simulation_repo_list_by_scenario(_db_session):
    from app.db.repository import SimulationRepo

    _seed_scenario(_db_session)
    repo = SimulationRepo(_db_session)
    repo.create(session_id="sim-a", scenario_id="repo_test_sc", decision_vars={}, world_state={})
    repo.create(session_id="sim-b", scenario_id="repo_test_sc", decision_vars={}, world_state={})

    rows = repo.list_by_scenario("repo_test_sc")
    assert len(rows) == 2
    ids = {r.id for r in rows}
    assert "sim-a" in ids
    assert "sim-b" in ids


# ── EventRepo ────────────────────────────────────────────────


def test_event_repo_save_and_get(_db_session):
    from app.db.repository import EventRepo

    _seed_scenario(_db_session)
    # 先建一个 session
    from app.db.repository import SimulationRepo
    srepo = SimulationRepo(_db_session)
    srepo.create(session_id="sim-ev", scenario_id="repo_test_sc", decision_vars={}, world_state={})

    repo = EventRepo(_db_session)
    repo.save(
        session_id="sim-ev",
        year=1,
        agent="market",
        action="expand",
        state_diff={"cash_flow": -50},
        payload={"event": "expansion"},
    )
    repo.save(
        session_id="sim-ev",
        year=1,
        agent="risk",
        action="warn",
        state_diff={"cash_flow": 0},
        payload={"event": "warning"},
    )

    events = repo.get_by_session("sim-ev")
    assert len(events) == 2
    agents = {e.agent for e in events}
    assert agents == {"market", "risk"}


def test_event_repo_save_batch(_db_session):
    from app.db.repository import EventRepo, SimulationRepo

    _seed_scenario(_db_session)
    srepo = SimulationRepo(_db_session)
    srepo.create(session_id="sim-batch", scenario_id="repo_test_sc", decision_vars={}, world_state={})

    repo = EventRepo(_db_session)
    batch = [
        {"session_id": "sim-batch", "year": 2, "agent": "market", "action": "a1", "state_diff": {}, "payload": {}},
        {"session_id": "sim-batch", "year": 2, "agent": "env", "action": "a2", "state_diff": {}, "payload": {}},
        {"session_id": "sim-batch", "year": 2, "agent": "personal", "action": "a3", "state_diff": {}, "payload": {}},
    ]
    repo.save_batch(batch)

    events = repo.get_by_session("sim-batch")
    assert len(events) == 3


def test_event_repo_get_empty_session(_db_session):
    from app.db.repository import EventRepo

    repo = EventRepo(_db_session)
    assert repo.get_by_session("no-events") == []


# ── ScenarioRepo ─────────────────────────────────────────────


def test_scenario_repo_upsert_new(_db_session):
    from app.db.repository import ScenarioRepo

    repo = ScenarioRepo(_db_session)
    row = repo.upsert(
        scenario_id="new_sc",
        title="新场景",
        decision_source={"version": 1},
    )
    assert row.id is not None
    assert row.scenario_id == "new_sc"

    # 幂等：相同 scenario_id 不重复
    row2 = repo.upsert(
        scenario_id="new_sc",
        title="新场景(更新)",
        decision_source={"version": 2},
    )
    assert row2.id == row.id
    assert row2.title == "新场景(更新)"


def test_scenario_repo_get(_db_session):
    from app.db.repository import ScenarioRepo

    repo = ScenarioRepo(_db_session)
    repo.upsert(scenario_id="get_sc", title="G", decision_source={})

    row = repo.get("get_sc")
    assert row is not None
    assert row.title == "G"

    assert repo.get("nonexistent") is None


# ── AgentMemoryRepo ──────────────────────────────────────────


def test_agent_memory_repo_save_and_get(_db_session):
    from app.db.repository import AgentMemoryRepo

    user = _seed_user(_db_session)
    repo = AgentMemoryRepo(_db_session)

    repo.save(
        user_id=user.id,
        agent_id="market",
        domain="创业",
        key="risk_tolerance",
        value={"level": "high"},
    )

    mem = repo.get(user_id=user.id, agent_id="market", domain="创业", key="risk_tolerance")
    assert mem is not None
    assert mem.value == {"level": "high"}


def test_agent_memory_repo_delete_by_domain(_db_session):
    from app.db.repository import AgentMemoryRepo

    user = _seed_user(_db_session)
    repo = AgentMemoryRepo(_db_session)

    repo.save(user_id=user.id, agent_id="risk", domain="创业", key="k1", value={})
    repo.save(user_id=user.id, agent_id="risk", domain="投资", key="k2", value={})

    deleted = repo.delete_by_domain(user_id=user.id, agent_id="risk", domain="创业")
    assert deleted == 1

    assert repo.get(user_id=user.id, agent_id="risk", domain="创业", key="k1") is None
    assert repo.get(user_id=user.id, agent_id="risk", domain="投资", key="k2") is not None
