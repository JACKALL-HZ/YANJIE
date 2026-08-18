import json
from pathlib import Path

import pytest

from app.core.errors import (
    InvalidScenarioIdError,
    ScenarioIdMismatchError,
    ScenarioNotFoundError,
)
from app.core.config import get_settings
from app.scenarios.loader import ScenarioLoader


def test_test_settings_default_to_stub():
    assert get_settings().llm_use_stub is True


def test_loader_reads_scenario_from_configured_root(tmp_path: Path):
    payload = {
        "scenario_id": "demo",
        "title": "Demo",
        "version": 1,
        "decision_vars": [
            {
                "name": "budget",
                "value_type": "integer",
                "required": True,
                "default": 200000,
            }
        ],
        "initial_world_state": {},
        "agents": [
            {
                "agent_id": agent_id,
                "name": agent_id,
                "stance": "test",
                "goal": "test",
                "action_ids": [f"{agent_id}.hold"],
            }
            for agent_id in ("market", "environment", "personal", "risk")
        ],
        "action_effects": [
            {
                "action_id": "market.hold",
                "effects": {},
                "reason_template": "test",
            }
        ],
        "intervention_effects": [],
        "end_conditions": {
            "bankrupt": {"metric": "cash_flow", "op": "<=", "threshold": 0},
            "goal_reached": None,
            "steady_state": None,
            "timeout_years": 1,
        },
        "intervention_rules": [],
    }
    (tmp_path / "demo.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    source = ScenarioLoader(tmp_path).load("demo")

    assert source.scenario_id == "demo"


def test_loader_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(InvalidScenarioIdError):
        ScenarioLoader(tmp_path).load("../demo")


def test_loader_reports_missing_scenario(tmp_path: Path):
    with pytest.raises(ScenarioNotFoundError):
        ScenarioLoader(tmp_path).load("missing")


def test_loader_rejects_filename_and_payload_id_mismatch(tmp_path: Path):
    (tmp_path / "demo.json").write_text(
        json.dumps({"scenario_id": "other"}),
        encoding="utf-8",
    )

    with pytest.raises(ScenarioIdMismatchError):
        ScenarioLoader(tmp_path).load("demo")
