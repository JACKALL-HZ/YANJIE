"""场景化路由 —— PRD §6.5.2 双级分类路由。

按领域（创业 / 职业 / 买房 / 投资 / 通用）分片，检索前先路由。
双级策略：关键词精确匹配 → LLM 兜底分类。
"""

from app.core.logging import get_logger
import json
import re

logger = get_logger(__name__)

# 关键词 → domain 映射表（一级：精确匹配）
_KEYWORD_DOMAIN_MAP: dict[str, list[str]] = {
    "education": [
        "考研", "备考", "调剂", "国家线", "研究生", "院校", "清华", "留学",
        "出国读书", "申请学校", "雅思", "托福", "硕士申请", "博士申请",
        "英国", "美国", "澳洲", "加拿大",
    ],
    "entrepreneurship": [
        "创业", "开店", "奶茶", "餐饮", "加盟", "零售", "店",
        "startup", "开店预算", "盈亏平衡", "成本结构",
        "营业执照", "食品证", "消防证", "卫生许可",
    ],
    "career": [
        "转行", "跳槽", "辞职", "晋升", "升职", "offer", "面试", "薪资",
        "职业规划", "升职", "裁员", "裸辞", "副业",
        "简历", "职业", "工作", "岗位",
    ],
    "housing": [
        "买房", "房价", "房贷", "首付", "月供", "公积金",
        "楼盘", "户型", "学区", "房产", "住宅", "公寓",
    ],
    "investment": [
        "投资", "股票", "基金", "理财", "定投", "A股",
        "ETF", "收益", "资产配置", "风险分散", "债券",
    ],
}

_SCENARIO_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("study_abroad", ("留学", "出国读书", "英国", "美国", "澳洲", "加拿大", "雅思", "托福", "工签")),
    ("grad_exam", ("考研", "备考", "调剂", "国家线", "研究生", "清华", "保研")),
    ("career_advance", ("晋升", "升职", "管理岗", "技术经理", "领导", "带团队")),
    ("job_hunting", ("秋招", "春招", "求职", "找工作", "简历", "面试", "offer")),
    ("house_purchase", ("买房", "房价", "房贷", "首付", "月供", "公积金", "楼盘", "户型", "学区")),
    ("investment", ("投资", "股票", "基金", "理财", "定投", "etf", "债券", "资产配置")),
    ("restaurant_startup", ("餐饮", "饭店", "餐厅", "小吃店")),
    ("retail_store", ("零售", "便利店", "服装店", "店铺")),
    ("saas_startup", ("saas", "软件创业", "订阅制", "软件产品")),
    ("milktea_startup", ("奶茶", "茶饮")),
)

_DEFAULT_SCENARIO_BY_DOMAIN = {
    "education": "grad_exam",
    "entrepreneurship": "general_startup",
    "career": "job_hunting",
    "housing": "house_purchase",
    "investment": "investment",
    "general": "general_startup",
}

_FOOD_STARTUP_KEYWORDS = (
    "铁锅炖", "火锅", "烧烤", "面馆", "面店", "牛肉面", "拉面", "快餐", "咖啡馆",
)
_KEYWORD_DOMAIN_MAP["entrepreneurship"].extend(_FOOD_STARTUP_KEYWORDS)
_ENTREPRENEURSHIP_INTENT_PATTERN = re.compile(
    r"(?:开|经营|创办|做)\s*(?:一家|一个)?\s*[^，。；,;]{0,12}"
    r"(?:店|馆|餐厅|公司|工作室|摊)"
)

# 二级：LLM 分类提示词（模型只接收中文说明，内部领域编号仍由程序保存）
_CLASSIFY_SYSTEM = """你是衍界的场景识别器。请根据用户描述判断其主要决策领域：
- 创业：开店、做生意、创办公司
- 教育：考研、留学、申请学校
- 职业：求职、跳槽、晋升、职业规划
- 买房：购房、房贷、首付、月供
- 投资：股票、基金、理财、资产配置
- 其他：无法归入以上领域

只能回复一个中文分类词：创业、教育、职业、买房、投资、其他。不要解释。"""

_DOMAIN_LABELS = {
    "创业": "entrepreneurship",
    "教育": "education",
    "职业": "career",
    "买房": "housing",
    "投资": "investment",
    "其他": "general",
}


def has_explicit_scene_signal(query: str) -> bool:
    """Return whether a turn names a decision domain rather than only parameters."""
    query_lower = query.lower()
    if _ENTREPRENEURSHIP_INTENT_PATTERN.search(query):
        return True
    return any(
        keyword.lower() in query_lower
        for keywords in _KEYWORD_DOMAIN_MAP.values()
        for keyword in keywords
    )


def classify_scene(query: str, llm: "BaseChatModel | None" = None) -> str:  # type: ignore[name-defined]
    """双级分类路由。

    1. 关键词精确匹配（不调 LLM，零延迟）
    2. 匹配不到时调快模型分类（传入 llm 参数时）
    3. 无 LLM 时 fallback 到 "general"

    Returns:
        领域标签: "entrepreneurship" | "career" | "housing" | "investment" | "general"
    """
    query_lower = query.lower()

    # 一级：关键词精确匹配
    for domain, keywords in _KEYWORD_DOMAIN_MAP.items():
        for kw in keywords:
            if kw.lower() in query_lower:
                logger.debug("classify_scene keyword match: %s → %s", kw, domain)
                return domain

    if _ENTREPRENEURSHIP_INTENT_PATTERN.search(query):
        logger.debug("classify_scene entrepreneurship pattern match")
        return "entrepreneurship"

    # 二级：LLM 兜底分类
    if llm is not None:
        logger.debug("classify_scene no keyword match, invoking LLM")
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=_CLASSIFY_SYSTEM),
                HumanMessage(content=query),
            ]
            response = llm.invoke(messages)
            raw = str(response.content).strip().lower()
            domain = _DOMAIN_LABELS.get(raw, raw)
            # 兼容模型返回纯文本、代码块或 {"domain": "education"}。
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    parsed_domain = str(parsed.get("domain", "")).strip().lower()
                    domain = _DOMAIN_LABELS.get(parsed_domain, parsed_domain)
            except json.JSONDecodeError:
                domain = _DOMAIN_LABELS.get(raw, raw)
            valid_domains = {"education", "entrepreneurship", "career", "housing", "investment", "general"}
            if domain in valid_domains:
                logger.debug("classify_scene LLM classified: %s → %s", query[:50], domain)
                return domain
            for candidate in valid_domains - {"general"}:
                if re.search(rf"\b{re.escape(candidate)}\b", raw):
                    return candidate
            logger.debug("classify_scene LLM returned invalid domain: %s", domain)
        except Exception:
            logger.warning("classify_scene LLM classification failed, fallback to general")

    logger.debug("classify_scene no keyword match, fallback to general")
    return "general"


def get_collection_for_domain(domain: str) -> str:
    """返回领域对应的向量库 collection 名称。"""
    return f"decision_kb_{domain}"


def select_scenario(query: str, domain: str) -> str:
    """根据输入中的具体意图，在领域内选择对应的场景。"""
    # 创业是一级入口；餐饮、茶饮、零售和 SaaS 是后续由 industry
    # 驱动的业态，不再被当作用户侧并列场景。
    query_lower = query.lower()
    if any(keyword in query_lower for keyword in _FOOD_STARTUP_KEYWORDS):
        return "restaurant_startup"
    for scenario_id, keywords in _SCENARIO_KEYWORDS:
        if any(keyword.lower() in query_lower for keyword in keywords):
            return scenario_id
    return _DEFAULT_SCENARIO_BY_DOMAIN.get(domain, "general_startup")
