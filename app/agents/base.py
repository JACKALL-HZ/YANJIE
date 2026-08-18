from app.agents.contracts import AgentContext
from app.agents.narration import (
    build_action_presentation,
    build_stub_reason,
    calculate_stub_confidence,
)
from app.engine.models import AgentAction


class StubAgent:
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name

    def propose(self, context: AgentContext) -> AgentAction:
        if context.agent_id != self.agent_id:
            raise ValueError(f"context agent mismatch: {context.agent_id}")
        if not context.allowed_action_ids:
            raise ValueError(f"agent has no allowed actions: {self.agent_id}")

        base_index = (context.year + len(self.agent_id)) % len(
            context.allowed_action_ids
        )
        # Judge 修订反馈存在时，偏移一位选择不同动作（模拟修订行为）
        if context.judge_feedback:
            base_index = (base_index + 1) % len(context.allowed_action_ids)
        action_id = context.allowed_action_ids[base_index]
        if not context.latest_decision and not context.user_message:
            position = "neutral"
        elif self.agent_id == "market":
            position = "support"
        elif self.agent_id == "risk":
            position = "oppose"
        else:
            position = "conditional"
        return AgentAction(
            agent_id=self.agent_id,
            action_id=action_id,
            reason=build_stub_reason(context, action_id),
            confidence=calculate_stub_confidence(context),
            generation_source="stub",
            llm_called=False,
            position=position,
            rag_status=context.rag_status,
            rag_sources=list(context.rag_sources),
            yearly_strategy=context.yearly_strategy,
            evidence=list(context.evidence),
            **build_action_presentation(context, action_id),
        )
