"""场景扩充测试 — 验证新增场景可正确加载"""
from pathlib import Path

import pytest

from app.scenarios.loader import ScenarioLoader
from app.schemas.decision_source import DecisionSource


SCENARIO_IDS = ["milktea_startup", "retail_store", "saas_startup", "restaurant_startup"]


@pytest.fixture
def loader():
    return ScenarioLoader(root=Path(__file__).resolve().parent.parent / "scenarios")


def test_loader_finds_all_scenarios(loader):
    """4 个场景文件全部可被发现"""
    all_scenarios = loader.list_all()
    assert len(all_scenarios) >= 4
    for sid in SCENARIO_IDS:
        assert sid in all_scenarios, f"{sid} not found in scenario list"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_parses_valid_schema(loader, scenario_id):
    """每个场景都可通过 Pydantic 校验"""
    source = loader.load(scenario_id)
    validated = DecisionSource.model_validate(source)
    assert validated.scenario_id == scenario_id
    assert len(validated.agents) == 4


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_has_4_agents(loader, scenario_id):
    """每个场景 4 个 Agent"""
    source = loader.load(scenario_id)
    agent_ids = [a.agent_id for a in source.agents]
    assert set(agent_ids) == {"market", "environment", "personal", "risk"}


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_action_effects_complete(loader, scenario_id):
    """每个 Agent 的每个 action 都有对应的 action_effect"""
    source = loader.load(scenario_id)
    all_action_ids = set()
    for agent in source.agents:
        all_action_ids.update(agent.action_ids)
    effect_ids = {e.action_id for e in source.action_effects}
    missing = all_action_ids - effect_ids
    assert not missing, f"Missing action_effects: {missing}"


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_end_conditions(loader, scenario_id):
    """每个场景有 bankrupt + goal_reached 结局条件"""
    source = loader.load(scenario_id)
    ec = source.end_conditions
    assert ec.bankrupt is not None
    assert ec.goal_reached is not None
    assert ec.timeout_years > 0


def test_scenario_industries_differ(loader):
    """不同场景有不同的默认行业"""
    industries = set()
    for sid in SCENARIO_IDS:
        source = loader.load(sid)
        dv = source.decision_vars
        industry = next((d.default for d in dv if d.name == "industry"), None)
        if industry:
            industries.add(industry)
    # 至少 3 个不同行业（场景设计意图）
    assert len(industries) >= 3, f"Expected >=3 industries, got {industries}"


def test_scenario_cities_differ(loader):
    """不同场景有不同的默认城市"""
    cities = set()
    for sid in SCENARIO_IDS:
        source = loader.load(sid)
        dv = source.decision_vars
        city = next((d.default for d in dv if d.name == "city"), None)
        if city:
            cities.add(city)
    assert len(cities) >= 3, f"Expected >=3 cities, got {cities}"
