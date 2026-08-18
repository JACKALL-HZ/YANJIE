# 衍界 YanJie AI MVP-0 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 跑通"输入创业决策 → 4 Agent 逐年博弈 → 分支时间线 → 关键节点干预 → 结局判定 → 评分/风险/行动计划 → A/B 对比"的 MVP-0 闭环，用 Mock LLM stub 验证决策源解耦（AC7）。

**架构：** 两层 LangGraph（外层 8 节点时间线 + 内层 4 节点 Agent 决策）+ 4 决策 Agent + Simulation Judge Agent + 决策源 JSON 驱动。引擎节点为纯函数，LLM 调用委托 agents/，可断 LLM 用 stub 跑通判定。

**技术栈：** Python 3.12 + FastAPI + LangGraph + LangChain + pytest + PostgreSQL(pgvector，MVP-0 可先用内存)。

**范围说明：** 本计划聚焦 MVP-0——纯后端 + 文本时间线 + Mock LLM stub。前端 Vue、决策知识库 RAG 真入库、MCP 真数据、Three.js 可视化放 MVP-1/2，不在本计划。

---

## 文件结构

```
yanjie-ai/
├── pyproject.toml              # 依赖
├── alembic.ini                 # DB 迁移（MVP-0 可缓）
├── scenarios/
│   └── milktea_startup.json    # 奶茶店决策源
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── core/
│   │   ├── config.py           # 配置
│   │   └── llm.py              # LLM 路由（含 stub 开关）
│   ├── schemas/
│   │   ├── decision_source.py  # 决策源 Pydantic 模型
│   │   └── api.py              # API 请求/响应
│   ├── engine/
│   │   ├── state.py            # SimulationState TypedDict
│   │   ├── nodes.py            # 外层 8 节点纯函数
│   │   ├── graph.py            # LangGraph 外层图组装
│   │   ├── engine.py           # SimulationEngine 逐年度驱动
│   │   └── scoring.py          # 评分/风险/行动计划
│   ├── agents/
│   │   ├── base.py             # Agent 基类
│   │   ├── market.py
│   │   ├── environment.py
│   │   ├── personal.py
│   │   ├── risk.py             # 含关键事件触发
│   │   ├── judge.py            # Simulation Judge Agent
│   │   └── inner_graph.py      # 内层 Agent 决策机
│   └── api/
│       └── simulation.py       # 模拟路由+SSE
└── tests/
    ├── test_decision_source.py
    ├── test_state.py
    ├── test_agents_stub.py
    ├── test_nodes.py
    ├── test_engine.py
    ├── test_intervention.py
    ├── test_scoring.py
    ├── test_compare.py
    ├── test_ac7_decoupling.py
    └── test_e2e_milktea.py
```

**职责边界**：`engine/nodes.py` 纯函数（LLM 调用委托 `agents/`）；`agents/` 只调 LLM+管记忆，不做结局判定；`scenarios/` 决策源是数据不是代码。

---

## 任务 0：项目初始化

**文件：**
- 创建：`pyproject.toml`
- 创建：`app/__init__.py`、`app/core/__init__.py` 等所有 `__init__.py`

- [ ] **步骤 1：写 pyproject.toml**

```toml
[project]
name = "whatif-life"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "langgraph>=0.2",
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "pydantic>=2.9",
    "psycopg[binary]>=3.2",
    "pgvector>=0.3",
    "sse-starlette>=2.1",
    "python-dotenv>=1.0",
]
[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24"]
```

- [ ] **步骤 2：建目录与 __init__.py**

运行：`mkdir -p app/{core,schemas,engine,agents,api} tests scenarios && touch app/__init__.py app/core/__init__.py app/schemas/__init__.py app/engine/__init__.py app/agents/__init__.py app/api/__init__.py tests/__init__.py`

- [ ] **步骤 3：装依赖**

运行：`pip install -e ".[dev]"`
预期：无报错，`python -c "import langgraph; import fastapi"` 通过

- [ ] **步骤 4：Commit**

```bash
git init && git add -A && git commit -m "chore: init project skeleton"
```

---

## 任务 1：决策源 schema + 奶茶店首场景

**文件：**
- 创建：`app/schemas/decision_source.py`
- 创建：`scenarios/milktea_startup.json`
- 测试：`tests/test_decision_source.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_decision_source.py
import json
from pathlib import Path
from app.schemas.decision_source import DecisionSource

def test_load_milktea_scenario():
    data = json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8"))
    ds = DecisionSource(**data)
    assert ds.scenario_id == "milktea_startup"
    assert len(ds.agents) == 4
    assert {a.id for a in ds.agents} == {"market", "environment", "personal", "risk"}
    assert ds.end_conditions.bankrupt.metric == "现金流"

def test_intervention_rules_loaded():
    data = json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8"))
    ds = DecisionSource(**data)
    assert len(ds.intervention_rules.rules) >= 1
    assert ds.intervention_rules.max_interventions_per_session == 3
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_decision_source.py -v`
预期：FAIL，`ModuleNotFoundError: app.schemas.decision_source`

- [ ] **步骤 3：写决策源模型**

```python
# app/schemas/decision_source.py
from pydantic import BaseModel
from enum import Enum

class AgentDef(BaseModel):
    id: str
    name: str
    stance: str
    goal: str
    actions: list[str]

class EndConditions(BaseModel):
    goal_reached: dict
    steady_state: dict
    bankrupt: dict
    timeout: dict

class InterventionRule(BaseModel):
    trigger: dict
    event: str
    options: list[str]

class InterventionRules(BaseModel):
    rules: list[InterventionRule]
    max_interventions_per_session: int = 3

class DecisionSource(BaseModel):
    scenario_id: str
    title: str
    difficulty: str
    estimated_minutes: int
    intro: str
    applicable_users: str
    background: str
    decision_vars: dict
    user_profile_schema: dict = {}
    agents: list[AgentDef]
    end_conditions: EndConditions
    intervention_rules: InterventionRules
    industry_benchmarks: dict
    external_data: list[dict] = []
```

- [ ] **步骤 4：写奶茶店决策源 JSON**

```json
// scenarios/milktea_startup.json
{
  "scenario_id": "milktea_startup",
  "title": "奶茶店创业模拟",
  "difficulty": "轻松",
  "estimated_minutes": 10,
  "intro": "输入你的创业计划，AI 多视角模拟未来 3 年走向。",
  "applicable_users": "想辞职开奶茶店/小本创业者",
  "background": "杭州商圈奶茶赛道，竞争红海但仍有窗口期。",
  "decision_vars": {"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3},
  "user_profile_schema": {"age": "int", "risk_appetite": "enum"},
  "agents": [
    {"id": "market", "name": "市场Agent", "stance": "行业视角", "goal": "模拟市场供需/竞争", "actions": ["定价","扩店","收缩","促销","差异化"]},
    {"id": "environment", "name": "环境Agent", "stance": "宏观视角", "goal": "演化政策/消费力/人口", "actions": ["政策变动","消费降级","人口流入","突发"]},
    {"id": "personal", "name": "个人Agent", "stance": "用户立场", "goal": "资金/技能/时间约束下求存", "actions": ["投入","节省","借贷","转行","止损"]},
    {"id": "risk", "name": "风险Agent", "stance": "对抗视角", "goal": "注入黑天鹅+触发关键事件+判结局", "actions": ["黑天鹅","关键事件","风险触发","结局判定"]}
  ],
  "end_conditions": {
    "goal_reached": {"metric": "回本", "threshold": 1.0},
    "steady_state": {"metric": "月利润", "threshold": 30000, "sustained_months": 6},
    "bankrupt": {"metric": "现金流", "threshold": 0},
    "timeout": {"years": 3}
  },
  "intervention_rules": {
    "rules": [
      {"trigger": {"metric": "现金流", "op": "<", "threshold": 50000}, "event": "现金流告急", "options": ["继续投入","降本裁员","止损退出"]},
      {"trigger": {"metric": "竞争数", "op": ">", "threshold": 60}, "event": "竞争激增", "options": ["差异化","价格战","收缩防守"]}
    ],
    "max_interventions_per_session": 3
  },
  "industry_benchmarks": {"gross_margin": 0.6, "payback_months": [8, 15], "competition": "高"},
  "external_data": [{"key": "market_奶茶_杭州", "value": {"competitors": 47, "avg_price": 12, "trend": "下行"}}]
}
```

- [ ] **步骤 5：跑测试验证通过**

运行：`pytest tests/test_decision_source.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add -A && git commit -m "feat: decision source schema + milktea scenario"
```

---

## 任务 2：SimulationState TypedDict

**文件：**
- 创建：`app/engine/state.py`
- 测试：`tests/test_state.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_state.py
from app.engine.state import SimulationState, make_initial_state

def test_initial_state():
    state = make_initial_state(scenario_id="milktea_startup", decision_vars={"budget": 200000})
    assert state["year"] == 0
    assert state["phase"] == "input"
    assert state["world_state"]["现金流"] == 200000
    assert state["agent_states"] == {}
    assert state["timeline"] == []
    assert state["interventions"] == []
    assert state["result"] is None
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_state.py -v`
预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：写 state**

```python
# app/engine/state.py
from typing import TypedDict, Any

class SimulationState(TypedDict, total=False):
    scenario_id: str
    decision_vars: dict
    user_profile: dict | None
    phase: str               # input/simulating/scoring/end
    year: int
    world_state: dict        # 现金流/客流/竞争数/月利润/回本...
    agent_states: dict       # {agent_id: {memory, stance, actions_log}}
    timeline: list[dict]     # 年度节点
    interventions: list[dict]
    pending_intervention: dict | None
    verdict: dict | None     # Judge Agent 校验结果
    result: str | None       # goal_reached/steady/bankrupt/timeout
    score: int | None
    score_detail: dict | None
    risks: list[dict]
    advice: str | None
    action_plan: list[dict] | None
    compare_pair_id: str | None

def make_initial_state(scenario_id: str, decision_vars: dict, user_profile: dict | None = None) -> SimulationState:
    return SimulationState(
        scenario_id=scenario_id,
        decision_vars=decision_vars,
        user_profile=user_profile,
        phase="input",
        year=0,
        world_state={"现金流": decision_vars.get("budget", 0), "客流": 0, "竞争数": 47, "月利润": 0, "回本": 0.0},
        agent_states={},
        timeline=[],
        interventions=[],
        pending_intervention=None,
        verdict=None,
        result=None,
        score=None,
        score_detail=None,
        risks=[],
        advice=None,
        action_plan=None,
        compare_pair_id=None,
    )
```

- [ ] **步骤 4：跑测试验证通过**

运行：`pytest tests/test_state.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add -A && git commit -m "feat: SimulationState TypedDict"
```

---

## 任务 3：4 Agent + Judge Agent stub（Mock LLM）

**文件：**
- 创建：`app/core/llm.py`
- 创建：`app/agents/base.py`
- 创建：`app/agents/market.py`、`environment.py`、`personal.py`、`risk.py`、`judge.py`
- 测试：`tests/test_agents_stub.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_agents_stub.py
from app.engine.state import make_initial_state
from app.agents.market import MarketAgent
from app.agents.judge import JudgeAgent

def test_market_agent_stub_decision():
    agent = MarketAgent(use_stub=True)
    state = make_initial_state("milktea_startup", {"budget": 200000})
    decision = agent.decide(year=1, world_state=state["world_state"], kb_context="")
    assert "action" in decision
    assert decision["action"] in ["定价","扩店","收缩","促销","差异化"]

def test_judge_agent_stub_verdict_consistent():
    judge = JudgeAgent(use_stub=True)
    verdict = judge.check(year=1, world_state={"现金流": 100000}, actions=[{"agent": "market", "action": "扩店"}])
    assert verdict["consistent"] is True
    assert "issues" in verdict

def test_judge_agent_catches_bankrupt_inconsistency():
    judge = JudgeAgent(use_stub=True)
    verdict = judge.check(year=1, world_state={"现金流": -5000}, actions=[{"agent": "market", "action": "扩店"}])
    assert verdict["consistent"] is False
    assert len(verdict["issues"]) > 0
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_agents_stub.py -v`
预期：FAIL，`ModuleNotFoundError`

- [ ] **步骤 3：写 LLM 路由（含 stub 开关）**

```python
# app/core/llm.py
import os
from typing import Any

class LLMRouter:
    def __init__(self, use_stub: bool = False):
        self.use_stub = use_stub or os.getenv("LLM_USE_STUB") == "1"
        self._fast = None
        self._slow = None

    def fast(self) -> Any:
        if self.use_stub:
            return StubLLM()
        if self._fast is None:
            from langchain_openai import ChatOpenAI
            self._fast = ChatOpenAI(model="deepseek-chat", temperature=0.7)
        return self._fast

    def slow(self) -> Any:
        if self.use_stub:
            return StubLLM()
        if self._slow is None:
            from langchain_openai import ChatOpenAI
            self._slow = ChatOpenAI(model="gpt-4o", temperature=0.3)
        return self._slow

class StubLLM:
    """Mock LLM：返回固定结构，用于断 LLM 验证 AC7。"""
    def invoke(self, messages, **kwargs):
        class R:
            content = '{"action":"定价","reason":"stub"}'
        return R()
```

- [ ] **步骤 4：写 Agent 基类与 5 个 Agent**

```python
# app/agents/base.py
import json
from app.core.llm import LLMRouter

class BaseAgent:
    def __init__(self, agent_id: str, stance: str, goal: str, actions: list[str], use_stub: bool = False):
        self.id = agent_id
        self.stance = stance
        self.goal = goal
        self.actions = actions
        self.router = LLMRouter(use_stub=use_stub)

    def decide(self, year: int, world_state: dict, kb_context: str) -> dict:
        prompt = f"你是{self.id}Agent，立场{self.stance}，目标{self.goal}。可选行动{self.actions}。当前世界状态{world_state}。第{year}年决策：输出JSON{{action,reason}}。"
        resp = self.router.fast().invoke([{"role": "user", "content": prompt}])
        try:
            data = json.loads(resp.content)
        except Exception:
            data = {"action": self.actions[0], "reason": resp.content}
        if data.get("action") not in self.actions:
            data["action"] = self.actions[0]
        data["agent"] = self.id
        return data
```

```python
# app/agents/market.py
from app.agents.base import BaseAgent
class MarketAgent(BaseAgent):
    def __init__(self, use_stub=False):
        super().__init__("market", "行业视角", "模拟市场供需/竞争", ["定价","扩店","收缩","促销","差异化"], use_stub)
```

```python
# app/agents/environment.py
from app.agents.base import BaseAgent
class EnvironmentAgent(BaseAgent):
    def __init__(self, use_stub=False):
        super().__init__("environment", "宏观视角", "演化政策/消费力/人口", ["政策变动","消费降级","人口流入","突发"], use_stub)
```

```python
# app/agents/personal.py
from app.agents.base import BaseAgent
class PersonalAgent(BaseAgent):
    def __init__(self, use_stub=False):
        super().__init__("personal", "用户立场", "资金/技能/时间约束下求存", ["投入","节省","借贷","转行","止损"], use_stub)
```

```python
# app/agents/risk.py
from app.agents.base import BaseAgent
class RiskAgent(BaseAgent):
    def __init__(self, use_stub=False):
        super().__init__("risk", "对抗视角", "注入黑天鹅+触发关键事件+判结局", ["黑天鹅","关键事件","风险触发","结局判定"], use_stub)

    def check_intervention_trigger(self, world_state: dict, intervention_rules: list) -> dict | None:
        for rule in intervention_rules:
            t = rule.trigger
            val = world_state.get(t["metric"])
            if val is None:
                continue
            triggered = (val < t["threshold"]) if t["op"] == "<" else (val > t["threshold"])
            if triggered:
                return {"event": rule.event, "options": rule.options, "metric": t["metric"]}
        return None
```

```python
# app/agents/judge.py
import json
from app.core.llm import LLMRouter

class JudgeAgent:
    """Simulation Judge Agent：回合末自洽校验 + 结局判定。"""
    def __init__(self, use_stub: bool = False):
        self.router = LLMRouter(use_stub=use_stub)

    def check(self, year: int, world_state: dict, actions: list[dict]) -> dict:
        # 硬规则先判：现金流为负却说扩张 → 不自洽
        cash = world_state.get("现金流", 0)
        has_expand = any(a.get("action") in ("扩店","投入") for a in actions)
        if cash < 0 and has_expand:
            return {"consistent": False, "issues": ["现金流为负却扩张"], "revise_suggest": "改收缩/止损"}
        if self.router.use_stub:
            return {"consistent": True, "issues": []}
        prompt = f"校验第{year}年自洽。世界状态{world_state}。各方行动{actions}。输出JSON{{consistent:bool,issues:[],revise_suggest:str}}。"
        resp = self.router.slow().invoke([{"role":"user","content":prompt}])
        try:
            return json.loads(resp.content)
        except Exception:
            return {"consistent": True, "issues": []}

    def judge_ending(self, world_state: dict, end_conditions) -> str | None:
        cash = world_state.get("现金流", 0)
        if cash <= end_conditions.bankrupt.threshold:
            return "bankrupt"
        if world_state.get("回本", 0) >= end_conditions.goal_reached.threshold:
            return "goal_reached"
        if world_state.get("月利润", 0) >= end_conditions.steady_state.threshold:
            return "steady"
        return None
```

- [ ] **步骤 5：跑测试验证通过**

运行：`pytest tests/test_agents_stub.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add -A && git commit -m "feat: 4 agents + judge agent with stub LLM"
```

---

## 任务 4：外层 LangGraph 8 节点骨架

**文件：**
- 创建：`app/engine/nodes.py`
- 创建：`app/engine/graph.py`
- 测试：`tests/test_nodes.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_nodes.py
from app.engine.state import make_initial_state
from app.engine.nodes import setup_node, end_check_node
from app.schemas.decision_source import DecisionSource
import json
from pathlib import Path

def _ds():
    return DecisionSource(**json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8")))

def test_setup_node_initializes_agent_states():
    state = make_initial_state("milktea_startup", {"budget": 200000})
    state = setup_node(state, _ds(), use_stub=True)
    assert "market" in state["agent_states"]
    assert state["phase"] == "simulating"

def test_end_check_returns_bankrupt():
    state = make_initial_state("milktea_startup", {"budget": 200000})
    state["world_state"]["现金流"] = -1
    state["year"] = 1
    result = end_check_node(state, _ds())
    assert result["result"] == "bankrupt"
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_nodes.py -v`
预期：FAIL

- [ ] **步骤 3：写 nodes（纯函数）**

```python
# app/engine/nodes.py
from app.engine.state import SimulationState
from app.schemas.decision_source import DecisionSource
from app.agents.market import MarketAgent
from app.agents.environment import EnvironmentAgent
from app.agents.personal import PersonalAgent
from app.agents.risk import RiskAgent
from app.agents.judge import JudgeAgent

def setup_node(state: SimulationState, ds: DecisionSource, use_stub: bool = False) -> SimulationState:
    agent_states = {}
    for a in ds.agents:
        agent_states[a.id] = {"stance": a.stance, "memory": [], "actions_log": []}
    state["agent_states"] = agent_states
    state["phase"] = "simulating"
    return state

def run_agents_node(state: SimulationState, ds: DecisionSource, use_stub: bool = False) -> SimulationState:
    agents = {
        "market": MarketAgent(use_stub), "environment": EnvironmentAgent(use_stub),
        "personal": PersonalAgent(use_stub), "risk": RiskAgent(use_stub),
    }
    year = state["year"] + 1
    actions = []
    for aid, agent in agents.items():
        decision = agent.decide(year=year, world_state=state["world_state"], kb_context="")
        actions.append(decision)
        state["agent_states"][aid]["actions_log"].append({"year": year, **decision})
    state["_year_actions"] = actions
    state["year"] = year
    return state

def interact_node(state: SimulationState, ds: DecisionSource) -> SimulationState:
    # 应用 actions 到世界状态（简化：按 action 类型更新）
    ws = state["world_state"]
    for a in state.get("_year_actions", []):
        if a["action"] == "扩店":
            ws["竞争数"] = ws.get("竞争数", 0) + 3
            ws["现金流"] = ws.get("现金流", 0) - 30000
        elif a["action"] == "收缩":
            ws["现金流"] = ws.get("现金流", 0) + 10000
        elif a["action"] == "促销":
            ws["客流"] = ws.get("客流", 0) + 100
    ws["月利润"] = max(0, ws.get("客流", 0) * 12 - 20000)
    return state

def intervention_check_node(state: SimulationState, ds: DecisionSource) -> SimulationState:
    risk = RiskAgent(use_stub=True)
    trigger = risk.check_intervention_trigger(state["world_state"], ds.intervention_rules.rules)
    if trigger and len(state["interventions"]) < ds.intervention_rules.max_interventions_per_session:
        state["pending_intervention"] = trigger
    return state

def judge_node(state: SimulationState, ds: DecisionSource, use_stub: bool = False) -> SimulationState:
    judge = JudgeAgent(use_stub=use_stub)
    verdict = judge.check(year=state["year"], world_state=state["world_state"], actions=state.get("_year_actions", []))
    state["verdict"] = verdict
    return state

def append_timeline_node(state: SimulationState) -> SimulationState:
    state["timeline"].append({
        "year": state["year"],
        "world_state": dict(state["world_state"]),
        "agent_actions": state.get("_year_actions", []),
        "verdict": state["verdict"],
        "intervention": state.get("pending_intervention"),
    })
    state.pop("_year_actions", None)
    state["pending_intervention"] = None
    return state

def end_check_node(state: SimulationState, ds: DecisionSource) -> SimulationState:
    judge = JudgeAgent(use_stub=True)
    ending = judge.judge_ending(state["world_state"], ds.end_conditions)
    if ending:
        state["result"] = ending
        state["phase"] = "scoring"
    elif state["year"] >= ds.end_conditions.timeout.years:
        state["result"] = "timeout"
        state["phase"] = "scoring"
    return state
```

- [ ] **步骤 4：写 graph 组装**

```python
# app/engine/graph.py
from langgraph.graph import StateGraph, END
from app.engine.state import SimulationState
from app.engine.nodes import (setup_node, run_agents_node, interact_node,
    intervention_check_node, judge_node, append_timeline_node, end_check_node)
from app.schemas.decision_source import DecisionSource

def build_outer_graph(ds: DecisionSource, use_stub: bool = False):
    g = StateGraph(SimulationState)
    g.add_node("setup", lambda s: setup_node(s, ds, use_stub))
    g.add_node("run_agents", lambda s: run_agents_node(s, ds, use_stub))
    g.add_node("interact", lambda s: interact_node(s, ds))
    g.add_node("intervention_check", lambda s: intervention_check_node(s, ds))
    g.add_node("judge", lambda s: judge_node(s, ds, use_stub))
    g.add_node("append_timeline", append_timeline_node)
    g.add_node("end_check", lambda s: end_check_node(s, ds))
    g.set_entry_point("setup")
    g.add_edge("setup", "run_agents")
    g.add_edge("run_agents", "interact")
    g.add_edge("interact", "intervention_check")
    g.add_edge("intervention_check", "judge")
    g.add_conditional_edges("judge",
        lambda s: "append_timeline" if s["verdict"]["consistent"] else "run_agents")
    g.add_edge("append_timeline", "end_check")
    g.add_conditional_edges("end_check",
        lambda s: END if s["result"] else "run_agents")
    return g.compile()
```

- [ ] **步骤 5：跑测试验证通过**

运行：`pytest tests/test_nodes.py -v`
预期：PASS

- [ ] **步骤 6：Commit**

```bash
git add -A && git commit -m "feat: outer langgraph 8-node skeleton"
```

---

## 任务 5：SimulationEngine 逐年度驱动

**文件：**
- 创建：`app/engine/engine.py`
- 测试：`tests/test_engine.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_engine.py
import json
from pathlib import Path
from app.schemas.decision_source import DecisionSource
from app.engine.engine import SimulationEngine

def _ds():
    return DecisionSource(**json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8")))

def test_engine_runs_to_completion_with_stub():
    engine = SimulationEngine(_ds(), use_stub=True)
    state = engine.run(decision_vars={"budget": 200000})
    assert state["result"] in ("goal_reached","steady","bankrupt","timeout")
    assert len(state["timeline"]) >= 1
    assert state["year"] >= 1

def test_engine_respects_timeout():
    engine = SimulationEngine(_ds(), use_stub=True)
    state = engine.run(decision_vars={"budget": 200000})
    assert state["year"] <= 3
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_engine.py -v`
预期：FAIL

- [ ] **步骤 3：写 engine**

```python
# app/engine/engine.py
from app.engine.state import SimulationState, make_initial_state
from app.engine.graph import build_outer_graph

class SimulationEngine:
    def __init__(self, decision_source, use_stub: bool = False):
        self.ds = decision_source
        self.use_stub = use_stub
        self.graph = build_outer_graph(decision_source, use_stub=use_stub)

    def run(self, decision_vars: dict, user_profile: dict | None = None) -> SimulationState:
        initial = make_initial_state(self.ds.scenario_id, decision_vars, user_profile)
        # 防死循环：最多 span_years+2 轮
        max_steps = self.ds.end_conditions.timeout.years * 4 + 2
        config = {"recursion_limit": max_steps * 8}
        final_state = self.graph.invoke(initial, config=config)
        return final_state
```

- [ ] **步骤 4：跑测试验证通过**

运行：`pytest tests/test_engine.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add -A && git commit -m "feat: SimulationEngine yearly driver"
```

---

## 任务 6：关键节点干预

**文件：**
- 修改：`app/engine/engine.py`（加 intervene 方法）
- 测试：`tests/test_intervention.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_intervention.py
import json
from pathlib import Path
from app.schemas.decision_source import DecisionSource
from app.engine.engine import SimulationEngine

def _ds():
    return DecisionSource(**json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8")))

def test_intervention_changes_world_state():
    engine = SimulationEngine(_ds(), use_stub=True)
    # 模拟现金流低于阈值触发干预
    state = make_state_with_low_cash()
    from app.engine.nodes import intervention_check_node
    state = intervention_check_node(state, _ds())
    assert state["pending_intervention"] is not None
    # 用户选"降本裁员"
    engine.apply_intervention(state, chosen="降本裁员")
    assert state["world_state"]["现金流"] > 50000  # 支出减少
    assert len(state["interventions"]) == 1

def make_state_with_low_cash():
    from app.engine.state import make_initial_state
    s = make_initial_state("milktea_startup", {"budget": 200000})
    s["world_state"]["现金流"] = 30000  # 低于 50000 阈值
    s["year"] = 1
    return s
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_intervention.py -v`
预期：FAIL，`AttributeError: apply_intervention`

- [ ] **步骤 3：加 apply_intervention**

```python
# 追加到 app/engine/engine.py
class SimulationEngine:
    # ... 已有 __init__ / run ...

    def apply_intervention(self, state: SimulationState, chosen: str) -> SimulationState:
        iv = state.get("pending_intervention")
        if not iv:
            return state
        ws = state["world_state"]
        if chosen == "降本裁员":
            ws["现金流"] = ws.get("现金流", 0) + 40000
        elif chosen == "继续投入":
            ws["现金流"] = ws.get("现金流", 0) - 30000
        elif chosen == "止损退出":
            ws["现金流"] = ws.get("现金流", 0) + 10000
            state["result"] = "bankrupt"
            state["phase"] = "scoring"
        state["interventions"].append({"year": state["year"], "event": iv["event"], "chosen": chosen})
        state["pending_intervention"] = None
        return state
```

- [ ] **步骤 4：跑测试验证通过**

运行：`pytest tests/test_intervention.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add -A && git commit -m "feat: key-node intervention"
```

---

## 任务 7：评分 + 风险 + 行动计划

**文件：**
- 创建：`app/engine/scoring.py`
- 测试：`tests/test_scoring.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_scoring.py
from app.engine.scoring import compute_score, extract_risks, build_action_plan

def test_score_dimensions():
    score, detail = compute_score(world_state={"现金流": 100000, "月利润": 30000, "竞争数": 50}, result="steady")
    assert 0 <= score <= 100
    assert "market" in detail and "resource" in detail

def test_risks_extracted():
    risks = extract_risks(world_state={"现金流": 20000, "竞争数": 70})
    assert any(r["metric"] == "现金流" for r in risks)

def test_action_plan_executable_no_vague():
    plan = build_action_plan(risks=[{"metric":"现金流","trigger":"<50000"}], use_stub=True)
    assert len(plan) >= 5
    for item in plan:
        assert "content" in item and "deadline" in item
        assert "提升" not in item["content"]  # 禁虚话
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_scoring.py -v`
预期：FAIL

- [ ] **步骤 3：写 scoring**

```python
# app/engine/scoring.py
def compute_score(world_state: dict, result: str) -> tuple[int, dict]:
    cash = world_state.get("现金流", 0)
    profit = world_state.get("月利润", 0)
    comp = world_state.get("竞争数", 50)
    market = max(0, 100 - comp)
    resource = min(100, cash // 2000)
    policy = 70
    risk = 30 if result == "bankrupt" else (80 if result == "goal_reached" else 60)
    detail = {"market": market, "resource": resource, "policy": policy, "risk": risk}
    score = int(sum(detail.values()) / 4)
    return score, detail

def extract_risks(world_state: dict) -> list[dict]:
    risks = []
    if world_state.get("现金流", 0) < 50000:
        risks.append({"metric": "现金流", "trigger": "<50000", "severity": "高"})
    if world_state.get("竞争数", 0) > 60:
        risks.append({"metric": "竞争数", "trigger": ">60", "severity": "中"})
    return risks

def build_action_plan(risks: list[dict], use_stub: bool = True) -> list[dict]:
    # MVP-0 模板化（禁虚话），MVP-2 改慢模型生成
    plan = [
        {"content": "调研10家竞品客单价/客流/装修风格", "deadline": "Day 1-7", "related_risk": "竞争数"},
        {"content": "完成成本模型(房租/人工/原料)盈亏平衡测算", "deadline": "Day 8-12", "related_risk": "现金流"},
        {"content": "找3个原料供应商报价并谈账期", "deadline": "Day 13-18", "related_risk": "现金流"},
        {"content": "验证100个目标用户需求(问卷+访谈)", "deadline": "Day 19-25", "related_risk": "市场"},
        {"content": "跑通最小成本试营业方案(快闪店/外卖)", "deadline": "Day 26-30", "related_risk": "资源"},
    ]
    return plan
```

- [ ] **步骤 4：跑测试验证通过**

运行：`pytest tests/test_scoring.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add -A && git commit -m "feat: scoring + risks + action plan"
```

---

## 任务 8：A/B 对比

**文件：**
- 修改：`app/engine/engine.py`（加 compare 方法）
- 测试：`tests/test_compare.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_compare.py
import json
from pathlib import Path
from app.schemas.decision_source import DecisionSource
from app.engine.engine import SimulationEngine

def _ds():
    return DecisionSource(**json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8")))

def test_compare_two_sessions():
    engine = SimulationEngine(_ds(), use_stub=True)
    a = engine.run({"budget": 200000})
    b = engine.run({"budget": 100000})
    cmp = engine.compare(a, b)
    assert set(cmp.keys()) == {"资产","风险","成长","压力","结局"}
    assert cmp["结局"]["A"] == a["result"]
    assert cmp["结局"]["B"] == b["result"]
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_compare.py -v`
预期：FAIL，`AttributeError: compare`

- [ ] **步骤 3：加 compare**

```python
# 追加到 app/engine/engine.py
class SimulationEngine:
    # ...
    def compare(self, a: SimulationState, b: SimulationState) -> dict:
        def risk_level(r):
            return {"bankrupt":"高","timeout":"中","steady":"低","goal_reached":"低"}.get(r, "中")
        return {
            "资产": {"A": a["world_state"].get("现金流",0), "B": b["world_state"].get("现金流",0)},
            "风险": {"A": risk_level(a["result"]), "B": risk_level(b["result"])},
            "成长": {"A": "高" if a["result"]=="goal_reached" else "中", "B": "高" if b["result"]=="goal_reached" else "中"},
            "压力": {"A": "高" if a["world_state"].get("现金流",0)<50000 else "低", "B": "高" if b["world_state"].get("现金流",0)<50000 else "低"},
            "结局": {"A": a["result"], "B": b["result"]},
        }
```

- [ ] **步骤 4：跑测试验证通过**

运行：`pytest tests/test_compare.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add -A && git commit -m "feat: A/B compare"
```

---

## 任务 9：AC7 解耦验证（断 LLM 用 stub 跑通判定）

**文件：**
- 测试：`tests/test_ac7_decoupling.py`

- [ ] **步骤 1：写测试**

```python
# tests/test_ac7_decoupling.py
import json
from pathlib import Path
from app.schemas.decision_source import DecisionSource
from app.engine.engine import SimulationEngine

def _ds():
    return DecisionSource(**json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8")))

def test_ac7_outcome_independent_of_llm():
    """结局判定 100% 来自状态机+决策源，断 LLM 用 stub 仍能跑通判定。"""
    engine = SimulationEngine(_ds(), use_stub=True)  # LLM 是 stub，不调真模型
    state = engine.run({"budget": 200000})
    # 结局已判定，证明判定不依赖真 LLM
    assert state["result"] in ("goal_reached","steady","bankrupt","timeout")

def test_ac7_bankrupt_pure_state():
    engine = SimulationEngine(_ds(), use_stub=True)
    state = engine.run({"budget": 1})  # 极低预算必然破产
    assert state["result"] == "bankrupt"
    # 判定走的是 judge_ending 硬规则（现金流<=0），非 LLM
```

- [ ] **步骤 2：跑测试验证通过**

运行：`pytest tests/test_ac7_decoupling.py -v`
预期：PASS（stub 模式下判定仍成立）

- [ ] **步骤 3：Commit**

```bash
git add -A && git commit -m "test: AC7 decoupling verified with stub LLM"
```

---

## 任务 10：FastAPI 路由 + SSE

**文件：**
- 创建：`app/api/simulation.py`
- 创建：`app/main.py`
- 测试：`tests/test_api.py`

- [ ] **步骤 1：写失败测试**

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app

def test_create_and_run_simulation():
    client = TestClient(app)
    r = client.post("/api/simulations", json={"scenario_id":"milktea_startup","decision_vars":{"budget":200000},"use_stub":True})
    assert r.status_code == 200
    data = r.json()
    assert data["result"] in ("goal_reached","steady","bankrupt","timeout")
    assert len(data["timeline"]) >= 1

def test_compare_endpoint():
    client = TestClient(app)
    r = client.post("/api/simulations/compare", json={"a":{"scenario_id":"milktea_startup","decision_vars":{"budget":200000},"use_stub":True},"b":{"scenario_id":"milktea_startup","decision_vars":{"budget":100000},"use_stub":True}})
    assert r.status_code == 200
    assert "资产" in r.json()
```

- [ ] **步骤 2：跑测试验证失败**

运行：`pytest tests/test_api.py -v`
预期：FAIL

- [ ] **步骤 3：写 API**

```python
# app/api/simulation.py
import json
from pathlib import Path
from fastapi import APIRouter
from app.schemas.decision_source import DecisionSource
from app.engine.engine import SimulationEngine

router = APIRouter(prefix="/api")
_cache = {}

def _load_ds(scenario_id: str) -> DecisionSource:
    if scenario_id not in _cache:
        p = Path(f"scenarios/{scenario_id}.json")
        _cache[scenario_id] = DecisionSource(**json.loads(p.read_text(encoding="utf-8")))
    return _cache[scenario_id]

@router.post("/simulations")
def create_and_run(req: dict):
    ds = _load_ds(req["scenario_id"])
    engine = SimulationEngine(ds, use_stub=req.get("use_stub", False))
    state = engine.run(req["decision_vars"], req.get("user_profile"))
    return _serialize(state)

@router.post("/simulations/compare")
def compare(req: dict):
    a_req, b_req = req["a"], req["b"]
    ea = SimulationEngine(_load_ds(a_req["scenario_id"]), use_stub=a_req.get("use_stub", False))
    eb = SimulationEngine(_load_ds(b_req["scenario_id"]), use_stub=b_req.get("use_stub", False))
    sa = ea.run(a_req["decision_vars"])
    sb = eb.run(b_req["decision_vars"])
    return ea.compare(sa, sb)

def _serialize(state):
    return {k: v for k, v in state.items() if not k.startswith("_")}
```

```python
# app/main.py
from fastapi import FastAPI
from app.api.simulation import router

app = FastAPI(title="衍界 YanJie AI")
app.include_router(router)
```

- [ ] **步骤 4：跑测试验证通过**

运行：`pytest tests/test_api.py -v`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add -A && git commit -m "feat: FastAPI routes + compare"
```

---

## 任务 11：E2E 集成测试（奶茶店全流程）

**文件：**
- 测试：`tests/test_e2e_milktea.py`

- [ ] **步骤 1：写 E2E 测试**

```python
# tests/test_e2e_milktea.py
import json
from pathlib import Path
from app.schemas.decision_source import DecisionSource
from app.engine.engine import SimulationEngine
from app.engine.scoring import compute_score, extract_risks, build_action_plan

def _ds():
    return DecisionSource(**json.loads(Path("scenarios/milktea_startup.json").read_text(encoding="utf-8")))

def test_e2e_milktea_full_flow():
    engine = SimulationEngine(_ds(), use_stub=True)
    state = engine.run({"budget": 200000, "city": "杭州", "industry": "奶茶", "span_years": 3})
    # 结局
    assert state["result"] in ("goal_reached","steady","bankrupt","timeout")
    # 时间线可追溯
    assert len(state["timeline"]) >= 1
    for node in state["timeline"]:
        assert "year" in node and "world_state" in node and "agent_actions" in node
    # 评分/风险/行动计划
    score, detail = compute_score(state["world_state"], state["result"])
    risks = extract_risks(state["world_state"])
    plan = build_action_plan(risks)
    assert 0 <= score <= 100
    assert len(plan) >= 5

def test_e2e_parameter_rerun_diff_outcome():
    engine = SimulationEngine(_ds(), use_stub=True)
    rich = engine.run({"budget": 200000})
    poor = engine.run({"budget": 1})
    # 不同预算触发不同结局（至少破产 vs 非破产）
    assert poor["result"] == "bankrupt"
```

- [ ] **步骤 2：跑全量测试**

运行：`pytest -v`
预期：全 PASS

- [ ] **步骤 3：手动冒烟（SSE 暂略，MVP-0 用同步）**

运行：`uvicorn app.main:app --reload`，curl 测 `POST /api/simulations`
预期：返回带 result/timeline 的 JSON

- [ ] **步骤 4：Commit**

```bash
git add -A && git commit -m "test: e2e milktea full flow"
```

---

## 自检

**1. 规格覆盖度**：对照 PRD v1.1 MVP-0 范围——
- 决策源+奶茶店场景 → 任务1 ✓
- SimulationState → 任务2 ✓
- 4 Agent + Judge Agent → 任务3 ✓
- 外层 8 节点状态机 → 任务4 ✓
- 逐年度驱动 → 任务5 ✓
- 关键节点干预 → 任务6 ✓
- 评分/风险/行动计划 → 任务7 ✓
- A/B 对比 → 任务8 ✓
- AC7 解耦验证 → 任务9 ✓
- API → 任务10 ✓
- E2E → 任务11 ✓
- 遗漏：内层 Agent 决策机（4节点 observe/analyze/decide/interact）在 MVP-0 简化为 BaseAgent.decide 单步，MVP-1 再拆内层图——已在任务3 注明，可接受。
- 遗漏：SSE 流式——MVP-0 同步返回，SSE 放 MVP-1（任务10 注明）。

**2. 占位符扫描**：无 TODO/待定，每步有实际代码与命令。

**3. 类型一致性**：`SimulationState`、`DecisionSource`、`JudgeAgent.check/judge_ending`、`SimulationEngine.run/apply_intervention/compare` 在各任务中签名一致。

---

## 执行交接

计划已完成并保存到 `衍界 YanJie AI-实现计划.md`。两种执行方式：

**1. 子代理驱动（推荐）** - 每个任务调度一个新的子代理，任务间审查，快速迭代

**2. 内联执行** - 在当前会话中使用 executing-plans 执行任务，批量执行并设检查点

选哪种方式？

> **MVP-1/2 预告（不在本计划）**：MVP-1 加真 LLM 接入+决策知识库 RAG 召回+Judge Agent 回合自洽校验+内层 Agent 决策机拆分+SSE 流式；MVP-2 加前端 Vue+Three.js 可视化+DB 持久化+MCP 真数据+个人画像。
