"""决策拆解助手 API —— 自然语言 → 结构化决策变量。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, get_settings
from app.core.config import Settings
from app.db.models import User
from app.services.breakdown_service import BreakdownService

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class BreakdownRequest(BaseModel):
    latest_query: str | None = Field(
        None,
        description="Latest user turn used to detect an explicit scene switch",
        max_length=2000,
    )
    query: str = Field(..., description="用户自然语言描述", max_length=2000)
    scenario_id: str | None = Field(None, description="指定场景 id，留空自动匹配", max_length=255)


@router.post("/breakdown")
def breakdown_query(
    body: BreakdownRequest,
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> dict:
    """将自然语言决策描述拆解为当前场景的结构化变量。

    示例: POST /api/assistant/breakdown
      {"query": "在杭州开奶茶店预算20万推演3年"}
    → {scenario_id: "study_abroad", extracted_vars: {target_country: "美国", ...}, ...}
    """
    service = BreakdownService(settings)
    result = service.breakdown(
        body.query,
        scenario_id=body.scenario_id,
        latest_query=body.latest_query,
    )
    return result.to_dict()
