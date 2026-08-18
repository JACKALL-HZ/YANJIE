"""场景库 API 端点 —— 场景列表、详情查询。

参数校验 + 响应序列化。业务逻辑委托 services/。
"""

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_scenario_service, get_scenario_service_with_db
from app.core.errors import ScenarioNotFoundError
from app.services.scenario_presenter import (
    present_agent,
    present_decision_var,
    present_state_metric,
)
from app.services.scenario_service import ScenarioService

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("")
def list_scenarios(
    scenario_service: ScenarioService = Depends(get_scenario_service_with_db),
) -> list[dict]:
    """返回所有本地已安装场景。"""
    return scenario_service.list_all()


@router.get("/{scenario_id}")
def get_scenario(
    scenario_id: str,
    scenario_service: ScenarioService = Depends(get_scenario_service),
) -> dict:
    """返回单个场景的完整元数据。"""
    try:
        source = scenario_service.get(scenario_id)
    except ScenarioNotFoundError:
        raise HTTPException(status_code=404, detail="scenario not found")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {
        "scenario_id": source.scenario_id,
        "title": source.title,
        "decision_vars": [present_decision_var(dv) for dv in source.decision_vars],
        "state_metrics": [
            present_state_metric(metric) for metric in source.state_metrics
        ],
        "agents": [present_agent(agent) for agent in source.agents],
        "action_descriptions": {
            effect.action_id: effect.reason_template
            for effect in source.action_effects
        },
    }
