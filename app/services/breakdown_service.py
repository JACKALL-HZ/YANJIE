"""决策拆解服务 —— 自然语言 → 结构化决策变量。

流程：
  1. 无 scenario_id → classify_scene 自动匹配场景域
  2. 加载场景 decision_vars schema
  3. LLM 结构化提取（stub 模式用规则匹配）
  4. Pydantic 校验 → 返回 extracted + missing + suggestions
"""

import json
import re
from typing import Any

from app.core.config import Settings, get_settings
from app.core.llm import build_llm
from app.core.sanitize import sanitize_user_input
from app.kb.classify_scene import classify_scene, has_explicit_scene_signal, select_scenario
from app.scenarios.loader import ScenarioLoader
from app.schemas.decision_source import DecisionSource
from app.services.scenario_presenter import DECISION_VAR_LABELS


def _format_bound(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)


class BreakdownResult:
    """拆解结果。"""

    def __init__(
        self,
        scenario_id: str,
        extracted_vars: dict[str, Any],
        missing_required: list[str],
        suggestions: str,
        domain: str | None = None,
        invalid_vars: dict[str, str] | None = None,
    ):
        self.scenario_id = scenario_id
        self.extracted_vars = extracted_vars
        self.missing_required = missing_required
        self.suggestions = suggestions
        self.domain = domain
        self.invalid_vars = invalid_vars or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "extracted_vars": self.extracted_vars,
            "missing_required": self.missing_required,
            "suggestions": self.suggestions,
            "domain": self.domain,
            "invalid_vars": self.invalid_vars,
        }


_BREAKDOWN_SYSTEM = """你是衍界的决策参数提取器。请根据用户描述，提取当前场景所需的结构化参数。

当前场景：{scenario_title}
只允许使用下面列出的字段（字段名必须完全一致）：
{var_schema}

规则：
1. 只提取用户明确说出的值，不要猜测，也不要补充列表之外的字段。
2. 缺失字段不要输出。
3. 中文金额统一换算为元，例如“100万”输出1000000，“3000元”输出3000。
4. 目标国家、目标专业、目标院校、城市等文本字段保留用户原意，不要用用户画像中的信息替换。
5. 只能返回 JSON 对象，不要返回解释文字。

示例仅说明格式：{{"city": "杭州", "budget": 200000}}"""


_BREAKDOWN_USER = """用户描述：{query}

请严格按照当前场景字段返回 JSON："""


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
    """从 LLM 响应中提取 JSON。"""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    balanced = _extract_balanced_json(text)
    if balanced:
        try:
            return json.loads(balanced)
        except json.JSONDecodeError:
            pass
    return None


class BreakdownService:
    """决策拆解业务逻辑。"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._llm = (
            build_llm(self.settings.fast_llm)
            if not self.settings.llm_use_stub
            else None
        )
        self._loader = ScenarioLoader(self.settings.scenario_dir)

    def breakdown(
        self,
        query: str,
        scenario_id: str | None = None,
        latest_query: str | None = None,
    ) -> BreakdownResult:
        """拆解自然语言查询为结构化决策变量。"""
        # 1. 确定场景
        detected_domain: str | None = None
        if scenario_id is None:
            domain = classify_scene(query, llm=self._llm)
            detected_domain = domain
            if domain == "general":
                return BreakdownResult(
                    scenario_id="",
                    extracted_vars={},
                    missing_required=[],
                    suggestions="请告诉我你准备做什么，例如考研、留学、求职、买房、投资或创业。",
                    domain=domain,
                )
            scenario_id = self._match_scenario(domain, query)
        elif latest_query and has_explicit_scene_signal(latest_query):
            # Use only the newest turn to detect an explicit scene switch. The
            # full query remains the extraction context for the selected schema.
            latest_domain = classify_scene(latest_query, llm=self._llm)
            detected_domain = latest_domain
            if latest_domain != "general":
                candidate = self._match_scenario(latest_domain, latest_query)
                if candidate != scenario_id:
                    scenario_id = candidate

        # 2. 加载场景 schema
        source = self._loader.load(scenario_id)
        var_schema = self._build_schema_text(source)

        # 3. 提取变量
        extracted, invalid_vars = self._filter_extracted_vars(
            source,
            self._extract_vars(query, source, var_schema),
        )

        # 4. 检测缺失必填项
        missing = self._check_missing(source, extracted)

        # 5. 生成建议
        suggestions = self._build_suggestions(missing, source, invalid_vars)

        return BreakdownResult(
            scenario_id=scenario_id,
            extracted_vars=extracted,
            missing_required=missing,
            suggestions=suggestions,
            domain=detected_domain,
            invalid_vars=invalid_vars,
        )

    def _match_scenario(self, domain: str, query: str) -> str:
        """将领域和用户输入映射到一个具体场景。"""
        return select_scenario(query, domain)

    def _build_schema_text(self, source: DecisionSource) -> str:
        """构建 schema 描述给 LLM。"""
        type_labels = {"integer": "整数", "number": "数字", "string": "文字"}
        lines = []
        for dv in source.decision_vars:
            label = DECISION_VAR_LABELS.get(dv.name, "决策条件")
            lines.append(
                f"- 内部字段名“{dv.name}”（中文含义：{label}）："
                f"类型={type_labels.get(dv.value_type, '文字')}，"
                f"是否必填={'是' if dv.required else '否'}，默认值={dv.default}"
                + (
                    f"，取值范围为{dv.minimum}至{dv.maximum}"
                    if dv.minimum is not None and dv.maximum is not None
                    else ""
                )
            )
        return "\n".join(lines)

    def _get_var_names(self, source: DecisionSource) -> set[str]:
        return {dv.name for dv in source.decision_vars}

    def _get_var_def(self, source: DecisionSource, name: str) -> Any | None:
        for dv in source.decision_vars:
            if dv.name == name:
                return dv
        return None

    @staticmethod
    def _is_explicit_llm_value(query: str, value: Any) -> bool:
        """Allow LLM-only text only when it is visibly present in the user input."""
        if not isinstance(value, str):
            return False
        normalized_value = re.sub(r"\s+", "", value)
        normalized_query = re.sub(r"\s+", "", query)
        return len(normalized_value) > 1 and normalized_value in normalized_query

    @staticmethod
    def _filter_extracted_vars(
        source: DecisionSource,
        extracted: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """分离符合 schema 的提取值与需要用户修正的无效值。

        参数提取模型可能在用户没有说明某个数值时补出 0 或其他猜测值。
        这些值不能覆盖场景示例，更不能进入推演状态机。
        """
        definitions = {definition.name: definition for definition in source.decision_vars}
        filtered: dict[str, Any] = {}
        invalid: dict[str, str] = {}

        for name, raw_value in extracted.items():
            definition = definitions.get(name)
            if definition is None or raw_value is None:
                continue

            value = raw_value
            if definition.value_type == "integer":
                if isinstance(value, bool):
                    invalid[name] = f"{DECISION_VAR_LABELS.get(name, name)}必须是整数"
                    continue
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
                if not isinstance(value, int):
                    invalid[name] = f"{DECISION_VAR_LABELS.get(name, name)}必须是整数"
                    continue
            elif definition.value_type == "number":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    invalid[name] = f"{DECISION_VAR_LABELS.get(name, name)}必须是数字"
                    continue
            elif definition.value_type == "string":
                if not isinstance(value, str) or not value.strip():
                    invalid[name] = f"{DECISION_VAR_LABELS.get(name, name)}不能为空"
                    continue
                value = value.strip()

            if definition.minimum is not None and value < definition.minimum:
                invalid[name] = (
                    f"{DECISION_VAR_LABELS.get(name, name)}不能低于 "
                    f"{_format_bound(definition.minimum)}"
                )
                continue
            if definition.maximum is not None and value > definition.maximum:
                invalid[name] = (
                    f"{DECISION_VAR_LABELS.get(name, name)}不能高于 "
                    f"{_format_bound(definition.maximum)}"
                )
                continue
            filtered[name] = value

        return filtered, invalid

    def _extract_vars(
        self,
        query: str,
        source: DecisionSource,
        var_schema: str,
    ) -> dict[str, Any]:
        """从查询中提取变量。stub 模式用简单规则匹配。"""
        if self._llm is None:
            return self._stub_extract(query, source)

        from langchain_core.messages import HumanMessage, SystemMessage

        safe_query = sanitize_user_input(query)

        messages = [
            SystemMessage(content=_BREAKDOWN_SYSTEM.format(
                scenario_title=source.title,
                var_schema=var_schema,
            )),
            HumanMessage(content=_BREAKDOWN_USER.format(query=safe_query)),
        ]
        response = self._llm.invoke(messages)
        data = _json_from_text(response.content)
        if data is None:
            data = {}
        deterministic = self._stub_extract(query, source)
        # Do not accept LLM guesses or scenario defaults as user-confirmed values.
        valid_keys = self._get_var_names(source)
        extracted = {
            key: value
            for key, value in data.items()
            if key in valid_keys
            and (key in deterministic or self._is_explicit_llm_value(query, value))
        }
        extracted.update(deterministic)
        return extracted

    def _stub_extract(self, query: str, source: DecisionSource) -> dict[str, Any]:
        """Stub 模式规则匹配。（MVP-0 确定性提取）"""
        extracted: dict[str, Any] = {}
        valid_names = self._get_var_names(source)

        # 金额提取：按字段语义匹配，避免把留学/买房字段误套成创业字段。
        amount_pattern = (
            r"(?:预算|启动资金|可用资金|学费|资金)\s*"
            r"(?:约|为|是|有|：|:)?\s*"
            r"(\d[\d,]*(?:\.\d+)?)\s*(万元|万|元)?"
        )
        budget_match = re.search(amount_pattern, query)
        if budget_match and "budget" in valid_names:
            extracted["budget"] = self._parse_amount(
                budget_match.group(1), budget_match.group(2)
            )

        # 城市提取
        cities = ["杭州", "上海", "北京", "深圳", "广州", "成都", "武汉", "南京"]
        cities.extend(["长沙", "重庆", "西安", "合肥", "福州", "厦门"])
        for city in cities:
            if city in query and "city" in valid_names:
                extracted["city"] = city
                break
        if "city" in valid_names and "city" not in extracted:
            city_match = re.search(
                r"(?:在|位于)\s*([\u4e00-\u9fff]{2,6})(?=[，。；,;])",
                query,
            )
            if city_match:
                extracted["city"] = city_match.group(1)

        # 行业提取
        industries = {
            "奶茶": "milk_tea",
            "咖啡": "coffee",
            "餐饮": "catering",
            "零售": "retail",
        }
        for cn, en in industries.items():
            if cn in query and "industry" in valid_names:
                extracted["industry"] = en
                break
        if "industry" in valid_names and "industry" not in extracted:
            industry_match = re.search(
                r"(?:开|经营|做|主营)\s*(?:一家|一个)?\s*(?:独立品牌)?\s*"
                r"([^，。；,;]{1,20}?)(?:店|馆|餐厅|公司|工作室|项目|业务)?(?:[，。；,;]|$)",
                query,
            )
            if industry_match:
                industry = industry_match.group(1).strip()
                if industry:
                    extracted["industry"] = industry

        # 推演年数
        year_match = re.search(r"(\d+)\s*年", query)
        if year_match and "span_years" in valid_names:
            extracted["span_years"] = int(year_match.group(1))

        month_match = re.search(r"([0-9一二三四五六七八九十]+)\s*个?月", query)
        if month_match and "prep_months" in valid_names:
            extracted["prep_months"] = self._parse_number(month_match.group(1))

        if "target_school" in valid_names:
            school_match = re.search(r"([\u4e00-\u9fff]{2,12}大学)", query)
            if school_match:
                extracted["target_school"] = re.sub(
                    r"^(?:目标(?:院校)?|报考|考取|申请)", "", school_match.group(1)
                )

        if "current_level" in valid_names:
            for level in ("普通本科", "双非本科", "985", "211", "专科", "本科"):
                if level in query:
                    extracted["current_level"] = level
                    break

        if "target_country" in valid_names:
            for country in ("英国", "美国", "澳大利亚", "澳洲", "加拿大", "新加坡", "香港"):
                if country in query:
                    extracted["target_country"] = country
                    break

        if "target_major" in valid_names:
            major_match = re.search(
                r"(?:目标专业|专业|方向|研究方向)\s*(?:是|为|：|:)?\s*([^，。；,;\s]+)",
                query,
            )
            if major_match:
                extracted["target_major"] = major_match.group(1).strip()
            else:
                degree_match = re.search(
                    r"([\u4e00-\u9fffA-Za-z0-9+]{2,20})\s*(?:硕士|博士|本科)",
                    query,
                )
                if degree_match:
                    major = degree_match.group(1).strip()
                    for country in ("美国", "英国", "澳大利亚", "澳洲", "加拿大", "新加坡", "香港"):
                        major = major.replace(country, "")
                    major = re.sub(r"^(?:去|申请|读|留学)", "", major).strip()
                    if major:
                        extracted["target_major"] = major

        if "years_experience" in valid_names:
            experience_match = re.search(r"(\d+)\s*年(?:工作)?经验", query)
            if experience_match:
                extracted["years_experience"] = int(experience_match.group(1))

        if "current_position" in valid_names:
            position_match = re.search(r"从([^，。；,;]+?)(?:晋升|升职|升到|转为)", query)
            if position_match:
                extracted["current_position"] = position_match.group(1).strip()

        if "target_position" in valid_names:
            target_position_match = re.search(r"(?:晋升|升职|升到|转为)([^，。；,;]+)", query)
            if target_position_match:
                extracted["target_position"] = target_position_match.group(1).strip()

        if "investment_amount" in valid_names:
            investment_match = re.search(
                r"(?:投资|拿出|投入)\s*(?:约|为|是|：|:)?\s*(\d+(?:\.\d+)?)\s*(万|元)?",
                query,
            )
            if investment_match:
                extracted["investment_amount"] = self._parse_amount(
                    investment_match.group(1), investment_match.group(2)
                )

        if "income" in valid_names:
            income_match = re.search(
                r"(?:月收入|月薪|收入)\s*(?:约|为|是|：|:)?\s*(\d+(?:\.\d+)?)\s*(万|元)?",
                query,
            )
            if income_match:
                extracted["income"] = self._parse_amount(
                    income_match.group(1), income_match.group(2)
                )

        if "salary_expectation" in valid_names:
            salary_match = re.search(
                r"(?:期望薪资|期望月薪|目标薪资)\s*(?:约|为|是|：|:)?\s*(\d+(?:\.\d+)?)\s*(万|元)?",
                query,
            )
            if salary_match:
                extracted["salary_expectation"] = self._parse_amount(
                    salary_match.group(1), salary_match.group(2)
                )

        if "target_industry" in valid_names:
            industry_match = re.search(
                r"(?:目标行业|行业)\s*(?:是|为|：|:)?\s*([^，。；,;\s]+)",
                query,
            )
            if industry_match:
                extracted["target_industry"] = industry_match.group(1).strip()

        if "risk_level" in valid_names:
            risk_levels = {
                "保守": "conservative",
                "稳健": "balanced",
                "平衡": "balanced",
                "激进": "aggressive",
            }
            for cn, value in risk_levels.items():
                if cn in query:
                    extracted["risk_level"] = value
                    break

        return extracted

    @staticmethod
    def _parse_number(raw: str) -> int:
        if raw.isdigit():
            return int(raw)
        values = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        if raw == "十":
            return 10
        if "十" in raw:
            left, _, right = raw.partition("十")
            return values.get(left, 1) * 10 + values.get(right, 0)
        return values.get(raw, 0)

    @staticmethod
    def _parse_amount(number: str, unit: str | None) -> int:
        value = float(number.replace(",", ""))
        if unit in {"万", "万元"}:
            value *= 10000
        return int(value)

    def _check_missing(
        self,
        source: DecisionSource,
        extracted: dict[str, Any],
    ) -> list[str]:
        """检查必填决策变量是否有缺失。"""
        missing = []
        for dv in source.decision_vars:
            if dv.required and (dv.name not in extracted or extracted[dv.name] is None):
                missing.append(dv.name)
        return missing

    def _build_suggestions(
        self,
        missing: list[str],
        source: DecisionSource,
        invalid_vars: dict[str, str] | None = None,
    ) -> str:
        """为缺失的必填变量生成建议文案。"""
        invalid_messages = list((invalid_vars or {}).values())
        if not missing and not invalid_messages:
            return "所有决策变量已提取，可直接开始推演。"
        parts = []
        if invalid_messages:
            parts.append(f"请修正：{'；'.join(invalid_messages)}")
        if missing:
            missing_cn = [DECISION_VAR_LABELS.get(name, "决策条件") for name in missing]
            parts.append(f"请补充：{'、'.join(missing_cn)}")
        for m in missing:
            dv = self._get_var_def(source, m)
            if dv is not None and dv.default is not None:
                parts.append(
                    f"  - 例如：{DECISION_VAR_LABELS.get(m, '决策条件')} = {dv.default}"
                )
        return "\n".join(parts)
