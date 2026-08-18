from dataclasses import dataclass, field
from typing import Protocol

from app.engine.models import AgentAction
from app.schemas.domain_models import AgentEvidence


@dataclass(frozen=True)
class AgentContext:
    agent_id: str
    year: int
    world_state: dict[str, float]
    decision_vars: dict[str, object]
    allowed_action_ids: tuple[str, ...]
    agent_stance: str = ""  # 场景中定义的 Agent 立场，给 Judge 评审用
    rag_context: str = ""  # RAG 检索注入的知识片段（格式化文本）
    search_context: str = ""  # Tavily 实时搜索注入的信息
    yearly_strategy: str = "steady"  # 本年度用户策略指令: aggressive|steady|conservative
    user_profile_summary: str = ""  # 用户画像自然语言摘要
    user_message: str = ""  # 逐年交互模式下用户的消息
    judge_feedback: str = ""  # Judge 修订循环反馈：conflicts + recommendations
    constraint_note: str = ""  # 上轮分歧形成的中文动作边界
    variation_seed: str = ""  # 每次推演的随机种子，注入 prompt 促使不同策略探索
    latest_decision: str = ""
    scenario_id: str = ""
    scenario_title: str = ""
    scenario_brief: str = ""
    action_descriptions: dict[str, str] = field(default_factory=dict)
    rag_status: str = "disabled"
    rag_sources: tuple[str, ...] = ()
    evidence: list[AgentEvidence] = field(default_factory=list)


class AgentProtocol(Protocol):
    agent_id: str

    def propose(self, context: AgentContext) -> AgentAction:
        ...
