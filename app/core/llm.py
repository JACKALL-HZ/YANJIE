"""LLM 工厂 + Stub 模式 + 分层路由。

提供三个核心能力：
1. build_llm(LlmConfig) → ChatOpenAI  — 生产环境 LLM 实例
2. StubLLM                            — AC7 断 LLM 确定性 stub
3. LLMRouter                          — 快模型/慢模型/Stub 统一入口
"""

from dataclasses import dataclass
from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai import ChatOpenAI

from app.core.config import LlmConfig, Settings


# ── LLM 工厂 ──


def build_llm(cfg: LlmConfig) -> ChatOpenAI:
    """从 LlmConfig 构建 ChatOpenAI 实例。

    兼容 Ollama / vLLM / LM Studio 等任何 OpenAI 兼容 serving。
    """
    return ChatOpenAI(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        model=cfg.model,
        temperature=cfg.temperature,
        timeout=cfg.timeout,
        max_retries=cfg.max_retries,
    )


# ── Stub LLM（AC7 断 LLM 验证） ──


class StubLLM(BaseChatModel):
    """确定性 stub LLM —— 不调任何外部 API，返回固定结构 JSON。

    用于 AC7 验收：断 LLM 用 stub 跑通结局判定。
    实现 BaseChatModel 接口，可无痛替换 ChatOpenAI。
    """

    model: str = "stub"

    @property
    def _llm_type(self) -> str:
        return "stub-llm"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ):
        from langchain_core.outputs import ChatGeneration, ChatResult

        # 从消息内容推断返回类型
        content = str(messages[-1].content) if messages else ""
        if "conflicts" in content.lower() or "judge" in content.lower():
            response = (
                '{"judge_ok": true, "severity": 0.0, '
                '"conflicts": [], "recommendations": []}'
            )
        else:
            response = (
                '{"action_id": "market.differentiate", '
                '"reason": "根据当前世界状态选择该动作", "confidence": 0.5}'
            )

        generation = ChatGeneration(message=AIMessage(content=response))
        return ChatResult(generations=[generation])

    async def _agenerate(self, *args, **kwargs):
        return self._generate(*args, **kwargs)


# ── 分层模型路由 ──


class ModelTier(str, Enum):
    """模型层级。"""
    FAST = "fast"       # Agent 年度决策，80% 调用量
    SLOW = "slow"       # Judge 校验 + 行动计划
    STUB = "stub"       # AC7 确定性 stub


@dataclass
class LLMRouter:
    """快模型/慢模型/Stub 统一入口。

    用法：
        router = LLMRouter.from_settings(settings)
        fast_llm = router.fast()
        slow_llm = router.slow()
    """

    settings: Settings

    @classmethod
    def from_settings(cls, settings: Settings) -> "LLMRouter":
        return cls(settings=settings)

    def get(self, tier: ModelTier) -> BaseChatModel:
        """按层级获取 LLM 实例。"""
        if tier == ModelTier.STUB or self.settings.llm_use_stub:
            return StubLLM()
        if tier == ModelTier.SLOW:
            return build_llm(self.settings.slow_llm)
        return build_llm(self.settings.fast_llm)

    def fast(self) -> BaseChatModel:
        return self.get(ModelTier.FAST)

    def slow(self) -> BaseChatModel:
        return self.get(ModelTier.SLOW)


# ── 意图分类（PRD §8.3 前置路由节点） ──


def classify_intent(
    prompt: str,
    router: LLMRouter | None = None,
) -> str:
    """意图分类前置函数 —— 判断当前 LLM 调用属于哪种任务类型。

    MVP 阶段：stub 模式下恒返回 "agent_decision"；生产模式调快模型分类。
    返回值可驱动后续路由到 fast/slow 模型。

    Args:
        prompt: 待分类的 LLM prompt 文本
        router: LLM 路由器（None 时 stub）

    Returns:
        "agent_decision" | "judge_check" | "action_plan" | "scoring" | "other"
    """
    if router is None or router.settings.llm_use_stub:
        return "agent_decision"

    llm = router.fast()
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        response = llm.invoke([
            SystemMessage(
                content=(
                    "请判断这段衍界任务属于哪一种处理类型，只回复一个中文词："
                    "智能体决策、裁判校验、行动计划、评分或其他。"
                )
            ),
            HumanMessage(
                content=f"任务描述：{prompt[:500]}"
            ),
        ])
        content = str(response.content).lower()
        intent_labels = {
            "裁判校验": "judge_check",
            "行动计划": "action_plan",
            "评分": "scoring",
            "智能体决策": "agent_decision",
        }
        for label, intent in intent_labels.items():
            if label in content:
                return intent
        for intent in ["judge_check", "action_plan", "scoring", "agent_decision"]:
            if intent in content:
                return intent
        return "other"
    except Exception:
        return "agent_decision"
