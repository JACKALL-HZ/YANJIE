"""Server-side classification for paused simulation input."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


InputKind = Literal["question", "casual", "clarify", "business_decision", "sensitive"]


class InputIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: InputKind
    feedback: str


_CASUAL_PHRASES = frozenset({"好吧", "我想想", "我再想想", "再看看", "知道了"})
_QUESTION_MARKERS = (
    "什么", "为什么", "怎么", "如何", "多少", "哪个", "哪家", "谁", "什么时候", "在哪",
    "推荐", "建议", "分析", "比较", "介绍", "哪些", "几个",
)
_CLARIFY_MARKERS = ("说得", "讲得", "解释得", "更激进", "更保守", "详细一点", "具体一点")
_DECISION_MARKERS = ("请", "投", "加", "减少", "开", "选", "买", "卖", "代言", "预算", "招聘")
_SENSITIVE_MARKERS = (
    "自杀", "自残", "轻生", "伤害自己", "杀人", "伤害他人", "炸弹", "爆炸",
    "枪支", "毒品", "诈骗", "洗钱", "黑客入侵", "未成年色情",
)


def classify_input(
    text: str,
    known_decision_keywords: tuple[str, ...] = (),
) -> InputIntent:
    """Classify text without permitting it to change simulation state."""
    normalized = text.strip()
    if not normalized:
        raise ValueError("请输入具体问题或经营决策")
    if any(marker in normalized for marker in _SENSITIVE_MARKERS):
        return InputIntent(
            kind="sensitive",
            feedback="这类内容无法用于推演。我可以继续帮助你分析安全、合法的目标、选择和风险。",
        )
    if normalized in _CASUAL_PHRASES:
        return InputIntent(
            kind="casual",
            feedback="当前推演保持暂停，等你准备好再提交下一步决策。",
        )
    if normalized.endswith(("?", "？")) or any(
        marker in normalized for marker in _QUESTION_MARKERS
    ):
        return InputIntent(kind="question", feedback="这是一个问题，不会推进经营年度。")
    if any(marker in normalized for marker in _CLARIFY_MARKERS):
        return InputIntent(kind="clarify", feedback="我会先补充说明，当前推演保持暂停。")
    if any(keyword in normalized for keyword in known_decision_keywords):
        return InputIntent(kind="business_decision", feedback="已收到你的想法，正在结合当前推演继续分析。")
    if any(marker in normalized for marker in _DECISION_MARKERS):
        return InputIntent(kind="business_decision", feedback="已收到你的想法，正在结合当前推演继续分析。")
    return InputIntent(
        kind="business_decision",
        feedback="已收到你的想法，正在结合当前推演继续分析。",
    )
