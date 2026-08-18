"""风险传导 DAG 构建器 —— 纯函数，基于推演状态 + 场景 action_effects 构建。"""

from app.engine.models import SimulationState
from app.engine.scoring import extract_risks
from app.schemas.decision_source import DecisionSource
from app.schemas.risk_graph import RiskChain, RiskDag, RiskEdge, RiskNode

# 预定义传导关系：哪个指标下降会影响哪些指标
_PROPAGATION_RULES: list[tuple[str, str, str, float]] = [
    # (source, target, cause description, weight)
    ("cash_flow", "monthly_profit", "现金流紧张→无法投入营销和运营→月利润下降", 0.8),
    ("cash_flow", "payback_ratio", "现金流不足→延长回本周期", 0.6),
    ("competition_count", "customer_flow", "竞争加剧→分流客户→客流下降", 0.7),
    ("competition_count", "monthly_profit", "竞争加剧→价格战→利润率压缩", 0.6),
    ("customer_flow", "monthly_profit", "客流下降→营收减少→月利润下降", 0.9),
    ("customer_flow", "cash_flow", "客流下降→收入减少→现金储备消耗", 0.5),
    ("monthly_profit", "cash_flow", "持续亏损→现金储备消耗→现金流告急", 0.8),
    ("monthly_profit", "payback_ratio", "利润不足→回本周期延长", 0.7),
    ("payback_ratio", "cash_flow", "长期无法回本→现金储备持续消耗", 0.4),
]

# 传导链模板：多级级联
_CHAIN_TEMPLATES: list[dict] = [
    {
        "pathway": ["competition_count", "customer_flow", "monthly_profit", "cash_flow"],
        "description": "竞争加剧→客流下降→利润减少→现金流告急",
        "response_actions": [
            "差异化产品定位，减少直接价格竞争",
            "加大本地营销投入，提升复购率",
            "优化成本结构，降低盈亏平衡点",
            "准备应急资金，延长现金跑道",
        ],
    },
    {
        "pathway": ["cash_flow", "monthly_profit", "payback_ratio"],
        "description": "现金流紧张→运营收缩→利润持续下滑→回本无望",
        "response_actions": [
            "立即削减非必要支出",
            "寻找短期增收渠道（外卖/快闪）",
            "与供应商重新谈判账期",
            "评估是否止损退出",
        ],
    },
    {
        "pathway": ["customer_flow", "monthly_profit", "cash_flow", "payback_ratio"],
        "description": "客流持续下滑→营收不足→现金流告急→回本失败",
        "response_actions": [
            "重新定位目标客群",
            "调整定价策略",
            "削减固定成本",
            "评估关店/转型选项",
        ],
    },
]


def build_risk_dag(
    state: SimulationState,
    source: DecisionSource | None = None,
) -> RiskDag:
    """根据推演当前状态构建风险传导 DAG。

    Args:
        state: 当前模拟状态
        source: 决策源（用于读取 action_effects，可选）

    Returns:
        RiskDag 包含 nodes / edges / chains
    """
    ws = state.world_state.model_dump()
    risks = extract_risks(ws)

    # 1. 构建节点（仅包含有风险的指标）
    nodes = _build_nodes(ws, risks)

    # 2. 构建边（传导关系）
    edges = _build_edges(nodes, ws)

    # 3. 构建传导链
    chains = _build_chains(nodes, ws)

    return RiskDag(nodes=nodes, edges=edges, chains=chains)


def _build_nodes(ws: dict, risks: list) -> list[RiskNode]:
    nodes: list[RiskNode] = []
    metric_seen: set[str] = set()
    for risk in risks:
        metric = risk.metric
        if metric in metric_seen:
            continue
        metric_seen.add(metric)
        severity = _estimate_severity(risk)
        nodes.append(RiskNode(
            metric=metric,
            current_value=float(ws.get(metric) or 0),
            severity=severity,
            message=risk.message,
        ))
    return nodes


def _build_edges(nodes: list[RiskNode], ws: dict) -> list[RiskEdge]:
    node_metrics = {n.metric for n in nodes}
    edges: list[RiskEdge] = []
    for src, tgt, cause, weight in _PROPAGATION_RULES:
        if src in node_metrics or tgt in node_metrics:
            edges.append(RiskEdge(source=src, target=tgt, cause=cause, weight=weight))
    return edges


def _build_chains(nodes: list[RiskNode], ws: dict) -> list[RiskChain]:
    """根据当前世界状态判断哪些传导链被激活。"""
    node_metrics = {n.metric for n in nodes}
    chains: list[RiskChain] = []
    for tmpl in _CHAIN_TEMPLATES:
        pathway = tmpl["pathway"]
        # 链被激活条件：至少第一个节点在风险节点中
        if pathway[0] in node_metrics:
            chains.append(RiskChain(
                pathway=pathway,
                total_severity=_chain_severity(pathway, nodes),
                response_actions=tmpl["response_actions"],
            ))
    return chains


def _estimate_severity(risk) -> float:
    """从 RiskItem 提取 severity（已为 0-1 float）。"""
    return float(risk.severity)


def _chain_severity(pathway: list[str], nodes: list[RiskNode]) -> float:
    """计算传导链的综合严重程度。"""
    node_map = {n.metric: n.severity for n in nodes}
    total = sum(node_map.get(m, 0.0) for m in pathway)
    return min(1.0, total / max(1, len(pathway)))
