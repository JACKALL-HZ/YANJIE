"""LlmAgent：基于 ChatOpenAI 的决策 Agent，替代 StubAgent。"""

import json
import re
from collections.abc import Callable
from dataclasses import replace

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.contracts import AgentContext
from app.agents.narration import build_action_presentation, normalize_agent_reason
from app.core.sanitize import sanitize_rag_content, sanitize_user_input
from app.engine.models import AgentAction
from app.services.scenario_presenter import DECISION_VAR_LABELS


_STRATEGY_LABELS = {
    "aggressive": "激进扩张",
    "steady": "稳健推进",
    "conservative": "保守经营",
}
_POSITION_VALUES = {
    "support": "支持",
    "oppose": "反对",
    "conditional": "有条件支持",
    "neutral": "保持观察",
}
_POSITION_CODES = {value: key for key, value in _POSITION_VALUES.items()}


def _items(value: object, limit: int = 3) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


_SYSTEM_PROMPT = """你是 {name}，负责参与衍界决策推演。
角色内部编号：{agent_id}（仅供系统识别，不是展示名称）

你的立场：{stance}
你的目标：{goal}

你必须从下方允许的动作列表中精确选择一个。基于当前状态概况评估哪个动作最能推进你的目标。

{strategy_context}
请始终使用中文思考和生成说明。请回复一个 JSON 对象，包含以下字段：
- "action_id": 允许的动作内部编号之一（只用于程序识别）
- "recommendation": 用一句中文写清本角色建议执行什么，以及希望验证或达成什么
- "reason": 用一到两句中文写清判断依据，必须回应用户最新决策和本次专属分析简报
- "alternatives": 一到两个可执行的中文备选方案数组
- "objection": 用一句中文写清你反对、保留或需要补充验证的部分；没有时填写 null
- "stop_condition": 用一句中文写清何时应暂停、收缩或改走备选方案
- "confidence": 你对这个决策的信心，0 到 100 的整数
- "position": 对用户最新决策的立场，只能填写“支持”“反对”“有条件支持”或“保持观察”

说明约束：
- 不得复述世界状态中的原始数值、字段名或 JSON 内容；只可使用状态概况中的趋势和区间性判断。
- 优先依据“知识资料”与“外部资料”形成分析性结论，说明它们为什么支持或限制当前动作。
- 若没有检索资料，不得编造来源、政策或行业事实；应基于已给的状态概况给出条件性判断。
- 角色边界：市场角色只谈客群、产品、渠道和竞品；环境角色只谈当地条件、季节、政策或平台；个人角色只谈时间、能力、团队与执行负荷；风险角色只谈现金跑道、不可逆投入和止损条件。不得复述其他角色的结论。

只输出 JSON，不要其他文字。"""


_USER_PROMPT = """年份：{year}
决策变量：{decision_vars_json}

本次专属分析简报：
{scenario_brief}

当前状态概况（仅供趋势判断，不含绝对数值）：
{world_state_json}

{latest_decision_text}
{user_profile_text}允许的动作：
{allowed_actions_text}

{variation_hint}{judge_feedback}{constraint_note}{rag_context}{search_context}
请选择你的动作："""


_SYSTEM_PROMPT += """

本轮建议必须清晰回答：今年建议做什么、依据哪些用户实际条件、下一步做什么、什么信号会让建议失效、当前最大不确定项。返回 JSON 时额外包含：
- "key_factors": 2 到 3 条结合用户画像和当前状态的理由
- "next_actions": 1 到 3 条有完成标准的下一步
- "uncertainty": 当前最重要的未知条件，没有则为 null
yearly_strategy 只是用户偏好，不是强制命令；个人智能体必须先判断资金、时间、能力和家庭约束是否允许。
当 rag_status 不是 hit 时，不得声称有外部资料支持，只能基于用户输入、当前状态和场景规则分析。
只输出中文 JSON。
"""

_USER_PROMPT += """

本轮知识检索状态：{rag_status}
可引用来源：{rag_sources}
请给出一条年度主建议，不要输出空泛口号。
"""


def _untrusted_block(
    label: str,
    text: str,
    sanitizer: Callable[[str], str],
) -> str:
    cleaned = sanitizer(text)
    if not cleaned:
        return ""
    return f"[{label}]\n{cleaned}\n[END_{label}]"


def _extract_balanced_json(text: str) -> str | None:
    """从文本中提取第一个平衡的 { ... } JSON 字符串（支持嵌套）。"""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _json_from_text(text: str) -> dict | None:
    """从 LLM 响应中提取 JSON 对象。

    处理三种常见格式：
    1. 纯 JSON 字符串
    2. markdown 代码块包裹的 JSON
    3. 文本中嵌入的 JSON 对象（栈平衡提取，支持嵌套）
    """
    if not text:
        return None
    text = text.strip()
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试提取 markdown 代码块
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试平衡括号提取（支持嵌套 JSON）
    balanced = _extract_balanced_json(text)
    if balanced:
        try:
            return json.loads(balanced)
        except json.JSONDecodeError:
            pass
    return None


class LlmAgent:
    """基于 LLM 的决策 Agent，通过 prompt 指导模型在允许动作中选择。

    实现 AgentProtocol 的 propose 接口，可无缝替换 StubAgent。
    """

    def __init__(
        self,
        agent_id: str,
        name: str,
        stance: str,
        goal: str,
        allowed_action_ids: tuple[str, ...],
        action_descriptions: dict[str, str],
        llm: BaseChatModel,
    ):
        self.agent_id = agent_id
        self.name = name
        self.stance = stance
        self.goal = goal
        self.allowed_action_ids = allowed_action_ids
        self.action_descriptions = action_descriptions
        self.llm = llm

    def propose(self, context: AgentContext) -> AgentAction:
        if context.agent_id != self.agent_id:
            raise ValueError(f"context agent mismatch: expected {self.agent_id}, got {context.agent_id}")
        allowed = context.allowed_action_ids
        if not allowed:
            raise ValueError(f"agent has no allowed actions: {self.agent_id}")

        messages = self._build_messages(context)
        response = self.llm.invoke(messages)
        return self._parse(response.content, allowed, context)

    def _build_messages(self, context: AgentContext) -> list:
        sanitized_decision_vars = {
            key: (
                _untrusted_block(
                    "UNTRUSTED_USER_DATA",
                    value,
                    sanitize_user_input,
                )
                if isinstance(value, str)
                else value
            )
            for key, value in context.decision_vars.items()
        }
        context = replace(context, decision_vars=sanitized_decision_vars)

        action_lines = []
        for index, aid in enumerate(context.allowed_action_ids, start=1):
            desc = self.action_descriptions.get(aid, "(无描述)")
            action_lines.append(
                f"- 动作{index}：{desc}（内部编号：{aid}，仅用于结构化返回）"
            )

        # 策略指令上下文：仅个人智能体强制遵循，其他智能体知晓即可
        if self.agent_id == "personal":
            strategy_context = (
                f"重要：用户为本年度设定了策略指令："
                f"\"{_STRATEGY_LABELS.get(context.yearly_strategy, context.yearly_strategy)}\"。"
                f"你的决策必须与此策略对齐。"
                f"激进扩张 = 优先扩张和投资；"
                f"稳健推进 = 平衡增长与稳定；"
                f"保守经营 = 优先生存并削减成本。"
            )
        else:
            strategy_context = (
                f"用户的本年度策略指令为 "
                f"\"{_STRATEGY_LABELS.get(context.yearly_strategy, context.yearly_strategy)}\"，主要由个人智能体负责落实。"
            )

        if self.agent_id == "personal":
            strategy_context = (
                f"用户本年度偏好为：{_STRATEGY_LABELS.get(context.yearly_strategy, context.yearly_strategy)}。"
                "这只是偏好，不是必须执行的命令。请优先检查用户的资金、时间、能力、家庭负担和上一年度进展；"
                "如果偏好与实际承受能力冲突，明确解释冲突并给出可执行的折中建议。"
            )

        user_profile_text = (
            f"当前推演场景：{context.scenario_title or '未命名场景'}\n"
            "本次推演的事实以决策变量、世界状态和已提供的知识片段为准，"
            "不允许根据通用模板或猜测修改地点、数字和目标。\n"
        )
        if context.decision_vars.get("city"):
            user_profile_text += (
                f"本次推演目标城市：{context.decision_vars['city']}。"
                "用户画像中的常住地不能替换本次推演目标城市。\n"
            )
        if context.decision_vars.get("target_country"):
            user_profile_text += f"本次目标国家：{context.decision_vars['target_country']}。\n"
        if context.decision_vars.get("target_school"):
            user_profile_text += f"本次目标院校：{context.decision_vars['target_school']}。\n"
        if context.decision_vars.get("target_major"):
            user_profile_text += f"本次目标专业：{context.decision_vars['target_major']}。\n"

        user_profile_text += (
            "重要：决策变量中的城市是本次推演目标城市；用户画像中的现居城市只代表常住地，"
            "不能替换或覆盖本次推演目标城市。\n"
        )
        if context.user_profile_summary:
            user_profile_text += (
                f"用户画像：{_untrusted_block('UNTRUSTED_USER_DATA', context.user_profile_summary, sanitize_user_input)}\n"
            )
        if context.user_message:
            user_profile_text += (
                f"\n重要——用户本年度的留言：\"{_untrusted_block('UNTRUSTED_USER_DATA', context.user_message, sanitize_user_input)}\"\n"
                f"请在决策时考虑用户的意见。\n"
            )

        latest_decision_text = ""
        if context.latest_decision:
            latest_decision_text = (
                f"用户最新想法或决策：{_untrusted_block('UNTRUSTED_USER_DATA', context.latest_decision, sanitize_user_input)}\n"
                "请围绕这段内容和当前场景说明你的判断，不要重复通用模板。\n\n"
            )

        system = SystemMessage(content=_SYSTEM_PROMPT.format(
            name=self.name,
            agent_id=self.agent_id,
            stance=self.stance,
            goal=self.goal,
            strategy_context=strategy_context,
        ))
        world_state_text = self._format_world_state(context)
        judge_feedback_text = ""
        if context.judge_feedback:
            judge_feedback_text = (
                f"重要——裁判修订反馈：\n"
                f"{context.judge_feedback}\n"
                f"请根据此反馈调整你的决策。\n\n"
            )
        constraint_note_text = ""
        if context.constraint_note:
            constraint_note_text = (
                f"本轮硬约束：{context.constraint_note}\n"
                "只能从已收窄的允许动作中选择，不得推荐或返回其他动作。\n\n"
            )

        # 清洗外部内容（RAG 检索 + 搜索结果），防止回填注入
        sanitize_retrieved_data = lambda text: sanitize_rag_content(
            sanitize_user_input(text)
        )
        safe_rag = (
            _untrusted_block(
                "UNTRUSTED_RETRIEVED_DATA",
                context.rag_context,
                sanitize_retrieved_data,
            )
            if context.rag_context
            else ""
        )
        safe_search = (
            _untrusted_block(
                "UNTRUSTED_RETRIEVED_DATA",
                context.search_context,
                sanitize_retrieved_data,
            )
            if context.search_context
            else ""
        )

        # 随机种子注入：每次推演不同，促使智能体探索不同策略角度
        variation_hint = ""
        if context.variation_seed:
            variation_hint = (
                f"策略探索提示（种子 {context.variation_seed}）："
                f"尝试从略微不同的角度思考，如果多个动作都可行，认真权衡非常规选项。\n\n"
            )

        decision_vars_json = _untrusted_block(
            "UNTRUSTED_USER_DATA",
            json.dumps(
                {
                    DECISION_VAR_LABELS.get(key, key): value
                    for key, value in context.decision_vars.items()
                },
                ensure_ascii=False,
            ),
            sanitize_user_input,
        )
        scenario_brief = _untrusted_block(
            "UNTRUSTED_RETRIEVED_DATA",
            context.scenario_brief or "尚未生成专属分析简报，请仅根据用户条件和检索资料判断。",
            sanitize_retrieved_data,
        )

        user = HumanMessage(content=_USER_PROMPT.format(
            year=context.year,
            decision_vars_json=decision_vars_json,
            scenario_brief=scenario_brief,
            world_state_json=world_state_text,
            latest_decision_text=latest_decision_text,
            user_profile_text=user_profile_text,
            allowed_actions_text="\n".join(action_lines),
            variation_hint=variation_hint,
            judge_feedback=judge_feedback_text,
            constraint_note=constraint_note_text,
            rag_context=(safe_rag + "\n") if safe_rag else "",
            search_context=(safe_search + "\n") if safe_search else "",
            rag_status=context.rag_status,
            rag_sources=", ".join(context.rag_sources) or "无",
        ))
        return [system, user]

    @staticmethod
    def _format_world_state(context: AgentContext) -> str:
        """把内部数值压缩为定性状态，避免模型向用户复述模拟器原始指标。"""
        if context.scenario_id in {
            "study_abroad", "grad_exam",
        } or context.decision_vars.get("target_country") is not None \
                or context.decision_vars.get("target_school") is not None:
            labels = {
                "cash_flow": "可用预算",
                "customer_flow": "申请进展",
                "competition_count": "申请竞争压力",
                "monthly_profit": "阶段资金变化",
                "payback_ratio": "目标进度",
            }
        elif context.scenario_id in {"house_purchase"} or (
            context.decision_vars.get("city") is not None
            and context.decision_vars.get("income") is not None
        ):
            labels = {
                "cash_flow": "可用资金",
                "customer_flow": "看房进展",
                "competition_count": "市场压力",
                "monthly_profit": "月度结余变化",
                "payback_ratio": "购房可行度",
            }
        elif context.scenario_id in {"investment"} or context.decision_vars.get("investment_amount") is not None:
            labels = {
                "cash_flow": "可投资资产",
                "customer_flow": "组合分散度",
                "competition_count": "市场波动",
                "monthly_profit": "阶段收益变化",
                "payback_ratio": "目标进度",
            }
        elif context.scenario_id in {"career_advance", "job_hunting"} or (
            context.decision_vars.get("target_position") is not None
            or context.decision_vars.get("target_industry") is not None
        ):
            labels = {
                "cash_flow": "可支配资源",
                "customer_flow": "岗位机会进展",
                "competition_count": "岗位竞争压力",
                "monthly_profit": "收入变化",
                "payback_ratio": "职业目标进度",
            }
        else:
            labels = {
                "cash_flow": "现金流",
                "customer_flow": "客流量",
                "competition_count": "竞争数量",
                "monthly_profit": "月利润",
                "payback_ratio": "回本比例",
            }
        def qualitative_state(metric: str, value: float) -> str:
            if metric == "cash_flow":
                if value <= 0:
                    return "资金已耗尽，需要立即止损或补充资源"
                if value < 50_000:
                    return "资金缓冲非常紧张，难以承受大额试错"
                if value < 200_000:
                    return "资金缓冲有限，应优先验证再扩大投入"
                return "资金缓冲相对充足，但仍需控制不可逆投入"
            if metric == "customer_flow":
                if value <= 0:
                    return "尚未形成有效获客或进展验证"
                if value < 50:
                    return "获客与转化基础偏弱，需先验证需求"
                if value < 150:
                    return "获客仍在爬坡，适合优化转化与复购"
                return "获客基础较好，可评估规模化与效率"
            if metric == "competition_count":
                if value < 20:
                    return "外部竞争压力较低，存在探索窗口"
                if value < 40:
                    return "外部竞争处于中等水平，需明确差异化"
                return "外部竞争压力较高，不能只依赖同质化投入"
            if metric == "monthly_profit":
                if value < 0:
                    return "阶段收益为负，当前模式仍在消耗资源"
                if value == 0:
                    return "尚未形成稳定收益，需要先验证单位模型"
                if value < 10_000:
                    return "收益刚开始改善，尚不足以支撑激进扩张"
                return "已形成一定收益，可进一步评估投入回报"
            if metric == "payback_ratio":
                if value <= 0:
                    return "仍处于投入与验证初期"
                if value < 0.3:
                    return "回报验证不足，优先控制试错成本"
                if value < 0.7:
                    return "回报进度仍需观察，避免过早放大规模"
                return "回报已接近目标，可评估下一阶段增长"
            return "当前指标需要结合场景继续观察"

        return json.dumps(
            {
                labels.get(key, key): qualitative_state(key, value)
                for key, value in context.world_state.items()
            },
            ensure_ascii=False,
            indent=2,
        )

    def _parse(
        self,
        content: str,
        allowed: tuple[str, ...],
        context: AgentContext,
    ) -> AgentAction:
        data = _json_from_text(content)
        if data is None:
            presentation = build_action_presentation(context, allowed[0])
            return AgentAction(
                agent_id=self.agent_id,
                action_id=allowed[0],
                reason="模型返回内容无法解析，已回退到系统预设动作。",
                confidence=0.2,
                generation_source="fallback",
                llm_called=True,
                rag_status=context.rag_status,
                rag_sources=list(context.rag_sources),
                yearly_strategy=context.yearly_strategy,
                evidence=list(context.evidence),
                **presentation,
            )

        action_id = str(data.get("action_id", "")).strip()
        if action_id not in allowed:
            # 兼容模型按中文序号或动作说明返回，内部仍统一保存原动作编号。
            for index, allowed_id in enumerate(allowed, start=1):
                description = self.action_descriptions.get(allowed_id, "").strip()
                if action_id in {str(index), f"动作{index}", description}:
                    action_id = allowed_id
                    break
        presentation = build_action_presentation(context, action_id or allowed[0])
        reason = normalize_agent_reason(str(data.get("reason", "")).strip()) or "模型决策"

        recommendation = normalize_agent_reason(
            str(data.get("recommendation", "")).strip()
        ) or str(presentation["recommendation"])
        raw_alternatives = data.get("alternatives", [])
        if isinstance(raw_alternatives, str):
            raw_alternatives = [raw_alternatives]
        alternatives = [
            normalize_agent_reason(str(item).strip())
            for item in raw_alternatives
            if str(item).strip()
        ] if isinstance(raw_alternatives, list) else []
        if not alternatives:
            alternatives = list(presentation["alternatives"])
        objection_value = data.get("objection")
        objection = (
            normalize_agent_reason(str(objection_value).strip())
            if objection_value is not None and str(objection_value).strip()
            else presentation["objection"]
        )
        stop_condition_value = data.get("stop_condition")
        stop_condition = (
            normalize_agent_reason(str(stop_condition_value).strip())
            if stop_condition_value is not None and str(stop_condition_value).strip()
            else presentation["stop_condition"]
        )

        # 置信度由 LLM 自评（0-100），归一化到 0-1
        key_factors = [
            normalize_agent_reason(item)
            for item in _items(data.get("key_factors"))
        ]
        next_actions = [
            normalize_agent_reason(item)
            for item in _items(data.get("next_actions"))
        ]
        uncertainty_value = data.get("uncertainty")
        uncertainty = (
            normalize_agent_reason(str(uncertainty_value).strip())
            if uncertainty_value is not None and str(uncertainty_value).strip()
            else None
        )

        raw_conf = data.get("confidence")
        try:
            confidence = float(raw_conf) / 100.0 if raw_conf is not None else 0.7
            confidence = max(0.0, min(1.0, confidence))  # clamp [0, 1]
        except (ValueError, TypeError):
            confidence = 0.7

        if action_id not in allowed:
            fallback = allowed[0]
            reason = f"模型返回了未允许的动作，已改用系统预设动作。{reason}"
            action_id = fallback
            confidence = min(confidence, 0.3)  # 非法动作降低置信度

        raw_position = str(data.get("position", "保持观察")).strip()
        position = _POSITION_CODES.get(raw_position, raw_position.lower())
        if position not in _POSITION_VALUES:
            position = "neutral"

        return AgentAction(
            agent_id=self.agent_id,
            action_id=action_id,
            reason=reason,
            confidence=confidence,
            generation_source="llm",
            llm_called=True,
            position=position,
            recommendation=recommendation,
            key_factors=key_factors,
            next_actions=next_actions,
            uncertainty=uncertainty,
            alternatives=alternatives[:2],
            objection=objection,
            stop_condition=stop_condition,
            rag_status=context.rag_status,
            rag_sources=list(context.rag_sources),
            yearly_strategy=context.yearly_strategy,
            evidence=list(context.evidence),
        )
