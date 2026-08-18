"""Quantitative startup simulator used as the business-domain calculation core.

LLM and agents explain the simulation; this module owns every financial result.
"""

from copy import deepcopy
from typing import Any


class YanJieEngine:
    """Run a traceable quarterly startup simulation for a single business."""

    _REQUIRED = {"city", "district", "category", "total_budget", "total_years"}
    _CITY_FACTORS = {"北京": 1.35, "上海": 1.4, "杭州": 1.15, "深圳": 1.3, "广州": 1.15, "成都": 0.9}
    _CATEGORY = {
        "咖啡": {"price": 22.0, "margin": 0.62, "orders": 75.0, "rent": 9000.0, "staff": 10500.0},
        "奶茶": {"price": 16.0, "margin": 0.58, "orders": 105.0, "rent": 8500.0, "staff": 9600.0},
        "餐饮": {"price": 32.0, "margin": 0.55, "orders": 75.0, "rent": 10000.0, "staff": 12000.0},
    }
    _DECISIONS = {
        "steady_growth": {"orders": 1.20, "extra_cost": 2500.0, "margin_delta": -0.01, "risk": 2, "name": "稳健增长"},
        "precision_breakthrough": {"orders": 1.35, "extra_cost": 5000.0, "margin_delta": -0.05, "risk": 4, "name": "精准突破"},
        "defensive": {"orders": 0.88, "extra_cost": -6500.0, "margin_delta": 0.02, "risk": 1, "name": "收缩防守"},
        "shrink_stop_loss": {"orders": 0.82, "extra_cost": -9500.0, "margin_delta": 0.03, "risk": 1, "name": "收缩止损"},
        "transfer_or_close": {"orders": 0.0, "extra_cost": -18000.0, "margin_delta": 0.0, "risk": 1, "name": "转让闭店"},
    }

    # A conservative yearly strategy protects spend without treating ordinary
    # operation as a stop-loss event. shrink_stop_loss remains the true exit path.
    _DECISIONS["defensive"] = {
        "orders": 1.10,
        "extra_cost": -2500.0,
        "margin_delta": 0.01,
        "risk": 1,
        "name": "控速推进",
    }

    def __init__(self, raw_params: dict[str, Any]):
        missing = self._REQUIRED - set(raw_params)
        if missing:
            raise ValueError(f"缺少必要参数：{'、'.join(sorted(missing))}")
        if float(raw_params["total_budget"]) <= 0 or int(raw_params["total_years"]) <= 0:
            raise ValueError("总预算和推演周期必须大于 0")
        self.params = {
            "city": str(raw_params["city"]),
            "district": str(raw_params["district"]),
            "category": str(raw_params["category"]),
            "is_franchise": bool(raw_params.get("is_franchise", False)),
            "total_budget": round(float(raw_params["total_budget"]), 2),
            "total_years": int(raw_params["total_years"]),
            "granularity": str(raw_params.get("granularity", "quarter")),
        }
        if self.params["granularity"] != "quarter":
            raise ValueError("创业推演当前只支持季度粒度")

    def initialize(self) -> dict[str, Any]:
        """Build the opening ledger and protect the working-capital floor."""
        p = self.params
        profile = self._profile()
        # 创业推演必须保留足够的经营缓冲，否则首季度爬坡就会把
        # 账面资金全部耗尽，用户无法观察后续决策的真实差异。
        fixed_ratio = 0.60
        franchise = p["total_budget"] * 0.08 if p["is_franchise"] else 0.0
        working_cash = max(p["total_budget"] * 0.20, p["total_budget"] * (1 - fixed_ratio - (0.08 if p["is_franchise"] else 0)))
        fixed_investment = p["total_budget"] - working_cash
        budget_breakdown = [
            {"项目": "房租押金与首期", "金额": self._r(fixed_investment * 0.28)},
            {"项目": "装修与门头", "金额": self._r(fixed_investment * 0.30)},
            {"项目": "核心设备", "金额": self._r(fixed_investment * 0.25)},
            {"项目": "证照与首批原料", "金额": self._r(fixed_investment * 0.17 - franchise)},
            {"项目": "流动资金硬底线", "金额": self._r(working_cash)},
        ]
        if franchise:
            budget_breakdown.insert(3, {"项目": "加盟费与保证金", "金额": self._r(franchise)})
        breakeven = profile["fixed_cost"] / profile["effective_margin"] / 30 / profile["price"]
        return {
            "base_params": deepcopy(p), "budget_breakdown": budget_breakdown,
            "finance": {"remaining_cash": self._r(working_cash), "cumulative_revenue": 0.0, "cumulative_cost": self._r(fixed_investment), "cumulative_profit": self._r(-fixed_investment), "payback_progress": 0.0},
            "operation": {"daily_orders": profile["orders"], "avg_price": profile["price"], "gross_margin": profile["effective_margin"], "monthly_fixed_cost": profile["fixed_cost"], "breakeven_daily_orders": self._r(breakeven)},
            "history": {"rounds": [], "risk_events": []},
            "stage": {"current_round": 0, "total_rounds": p["total_years"] * 4, "is_game_over": False, "end_reason": None},
        }

    def decision_options(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Return concrete decisions. Stop-loss status suppresses growth."""
        alerts = self._stop_loss_reasons(state)
        if alerts:
            return [self._option("shrink_stop_loss"), self._option("transfer_or_close")]
        return [
            self._option("steady_growth"),
            self._option("precision_breakthrough"),
            self._option("defensive"),
            self._option("shrink_stop_loss"),
            self._option("transfer_or_close"),
        ]

    def advance(self, state: dict[str, Any], decision_id: str) -> dict[str, Any]:
        """Apply one decision to one quarter and append an immutable ledger row."""
        if state["stage"]["is_game_over"]:
            raise ValueError("推演已结束，不能继续决策")
        if decision_id not in {item["decision_id"] for item in self.decision_options(state)}:
            raise ValueError("当前决策不具体、不可用或违反止损约束")
        next_state = deepcopy(state)
        stage, op, finance = next_state["stage"], next_state["operation"], next_state["finance"]
        stage["current_round"] += 1
        effect = self._DECISIONS[decision_id]
        quarter_factor = (0.85, 1.0, 1.28, 0.90)[(stage["current_round"] - 1) % 4]
        ramp_factor = (0.78, 0.90, 1.0)[min(stage["current_round"] - 1, 2)]
        daily_orders = max(0.0, op["daily_orders"] * effect["orders"] * quarter_factor * ramp_factor)
        margin = max(0.35, min(0.72, op["gross_margin"] + effect["margin_delta"]))
        monthly_revenue = daily_orders * op["avg_price"] * 30
        monthly_cost = monthly_revenue * (1 - margin) + op["monthly_fixed_cost"] + effect["extra_cost"]
        quarter_revenue, quarter_cost = monthly_revenue * 3, monthly_cost * 3
        quarter_profit = quarter_revenue - quarter_cost
        finance["remaining_cash"] = self._r(
            max(0.0, finance["remaining_cash"] + quarter_profit)
        )
        finance["cumulative_revenue"] = self._r(finance["cumulative_revenue"] + quarter_revenue)
        finance["cumulative_cost"] = self._r(finance["cumulative_cost"] + quarter_cost)
        finance["cumulative_profit"] = self._r(finance["cumulative_revenue"] - finance["cumulative_cost"])
        finance["payback_progress"] = self._r(max(0.0, min(1.0, finance["cumulative_profit"] / state["base_params"]["total_budget"])))
        op.update({"daily_orders": self._r(daily_orders), "gross_margin": self._r(margin)})
        round_row = {"轮次": stage["current_round"], "决策": effect["name"], "日均单量": op["daily_orders"], "季度营收": self._r(quarter_revenue), "季度成本": self._r(quarter_cost), "季度利润": self._r(quarter_profit), "剩余现金": finance["remaining_cash"], "综合毛利率": op["gross_margin"]}
        next_state["history"]["rounds"].append(round_row)
        alerts = self._stop_loss_reasons(next_state)
        if alerts:
            next_state["history"]["risk_events"].append({"轮次": stage["current_round"], "预警": alerts})
        if decision_id == "transfer_or_close":
            stage.update({"is_game_over": True, "end_reason": "主动转让或闭店"})
        elif stage["current_round"] >= stage["total_rounds"]:
            stage.update({"is_game_over": True, "end_reason": "完成设定推演周期"})
        return next_state

    def agent_analysis(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """Expose non-overlapping quantitative views for the four agents."""
        op, finance, p = state["operation"], state["finance"], state["base_params"]
        demand = self._r(max(op["daily_orders"] * 18, op["breakeven_daily_orders"] * 1.8))
        runway = self._r(finance["remaining_cash"] / max(op["monthly_fixed_cost"], 1))
        alerts = self._stop_loss_reasons(state)
        if alerts:
            next_decision = "收缩止损：停止新增投入，压缩营业时段，先保住现金。"
        elif op["daily_orders"] < op["breakeven_daily_orders"]:
            next_decision = "精准突破：只选择一个获客渠道和一个主推产品，先把日均单量提高到保本线。"
        else:
            next_decision = "稳健增长：保持当前模型，连续观察复购和月净利润后再扩大投入。"
        return [
            {"智能体": "市场智能体", "置信度": "78%", "量化结论": f"市场只看需求和竞争：{p['city']}的{p['category']}模型日需求约 {demand:.0f} 单，当前门店日均 {op['daily_orders']:.2f} 单，预估市占率 {op['daily_orders']/max(demand,1):.1%}。本轮应优先验证高峰时段转化，不建议同时扩充品类。"},
            {"智能体": "环境智能体", "置信度": "74%", "量化结论": f"环境只看外部经营约束：{p['city']}当前模型固定成本约 {op['monthly_fixed_cost']:.0f} 元/月，综合毛利率约 {op['gross_margin']:.0%}。平台扣点和季节波动会直接压缩利润，选址和排班比盲目投放更重要。"},
            {"智能体": "个人智能体", "置信度": "76%", "量化结论": f"个人只看执行承载：当前方案需要创始人每日约 10-12 小时在岗，执行负荷 8/10。{next_decision}这是本年个人智能体推荐的下一步，不建议同时执行多个新增动作。"},
            {"智能体": "风险智能体", "置信度": "85%", "量化结论": f"风险只看损失边界：当前剩余现金 {finance['remaining_cash']:.2f} 元，可支撑约 {runway:.1f} 个月固定支出；日均单量止损线为 {op['breakeven_daily_orders']*0.8:.2f} 单，综合毛利率底线为45%。当前风险等级：{'高' if alerts else '中'}，必须先控制投入上限。"},
        ]

    def final_settlement(self, state: dict[str, Any]) -> dict[str, Any]:
        finance, op = state["finance"], state["operation"]
        rows = state["history"]["rounds"]
        attributions = []
        for row in (rows[:1] + rows[len(rows)//2:len(rows)//2+1] + rows[-1:]):
            if not row:
                continue
            nature = "正确" if row["季度利润"] >= 0 else "失误"
            attributions.append({"时间点": f"第{row['轮次']}轮", "决策动作": row["决策"], "量化影响": f"季度利润 {row['季度利润']:.2f} 元，日均单量 {row['日均单量']:.2f}", "性质": nature})
        return {"financial_table": {"初始总投入": state["base_params"]["total_budget"], "累计总营收": finance["cumulative_revenue"], "累计总成本": finance["cumulative_cost"], "最终剩余现金流": finance["remaining_cash"], "累计盈亏": finance["cumulative_profit"], "回本进度": finance["payback_progress"]}, "key_attributions": attributions, "optimal_path": [f"将日均单量稳定到 {op['breakeven_daily_orders']:.2f} 单以上，才进入扩张。", "现金低于总预算 15% 时立即执行收缩止损，不再追加增长投入。"], "scores": {"风险管控": self._score(finance["remaining_cash"] / state["base_params"]["total_budget"] * 100), "盈利能力": self._score(finance["payback_progress"] * 100), "资源效率": self._score(op["gross_margin"] * 130), "市场响应": self._score(op["daily_orders"] / op["breakeven_daily_orders"] * 60)}}

    def _profile(self) -> dict[str, float]:
        base = self._CATEGORY.get(self.params["category"], self._CATEGORY["餐饮"])
        factor = self._CITY_FACTORS.get(self.params["city"], 1.0)
        fixed = (base["rent"] * factor) + (base["staff"] * factor) + 3500 + 2800 + 1200
        effective_margin = base["margin"] - 0.20 * 0.45  # 45% 外卖订单，平台扣点 20%
        return {"price": base["price"], "margin": base["margin"], "orders": base["orders"], "fixed_cost": self._r(fixed), "effective_margin": self._r(effective_margin)}

    def _option(self, decision_id: str) -> dict[str, Any]:
        effect = self._DECISIONS[decision_id]
        if decision_id == "defensive":
            return {"decision_id": decision_id, "名称": effect["name"], "核心动作": ["只扩大已验证渠道", "控制非核心投入"], "预期收益": f"日单量变化 {(effect['orders']-1)*100:+.0f}%", "投入成本": f"月度增量成本 {effect['extra_cost']:+.0f} 元", "风险评级": "★" * effect["risk"] + "☆" * (5-effect["risk"])}
        return {"decision_id": decision_id, "名称": effect["name"], "核心动作": {"steady_growth": ["优化外卖菜单", "每周复盘复购"], "precision_breakthrough": ["集中投放高转化渠道", "推出限定产品"], "defensive": ["削减低效投放", "压缩非必要排班"], "shrink_stop_loss": ["停止新增投入", "压缩营业时段"], "transfer_or_close": ["评估转让", "清算库存与合同"]}[decision_id], "预期收益": f"日单量变化 {(effect['orders']-1)*100:+.0f}%", "投入成本": f"月度增量成本 {effect['extra_cost']:+.0f} 元", "风险评级": "★" * effect["risk"] + "☆" * (5-effect["risk"])}

    def _stop_loss_reasons(self, state: dict[str, Any]) -> list[str]:
        finance, op, rows = state["finance"], state["operation"], state["history"]["rounds"]
        reasons = []
        if finance["remaining_cash"] <= state["base_params"]["total_budget"] * 0.15: reasons.append("剩余现金触及总预算15%止损线")
        if len(rows) >= 2 and all(row["日均单量"] < op["breakeven_daily_orders"] * 0.8 for row in rows[-2:]): reasons.append("连续两轮日均单量低于止损线")
        if len(rows) >= 2 and all(row["综合毛利率"] < 0.45 for row in rows[-2:]): reasons.append("连续两轮综合毛利率低于45%")
        return reasons

    @staticmethod
    def _r(value: float) -> float: return round(float(value), 2)
    @staticmethod
    def _score(value: float) -> float: return round(max(0, min(100, value)), 2)
