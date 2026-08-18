# 衍界 YanJie AI MVP-0 后端实现计划

> **面向 agentic workers：** 实现本计划时必须逐任务执行，并在每个任务后运行该任务的验证命令。可使用 `subagent-driven-development` 或 `executing-plans`，但本仓库不自动提交或推送 Git。

**目标：** 在无真实 LLM、无数据库、无外部服务的条件下，跑通“决策变量 → 4 Agent 结构化行动 → 确定性状态推进 → 文本时间线 → 干预规则 → 结局/评分/风险/行动计划 → A/B 对比 → SSE 领域事件流”的 MVP-0 后端闭环。

**架构：** 决策源 JSON 是唯一业务事实来源；Pydantic 模型负责输入输出；外层 LangGraph 负责年度阶段路由，内层协调器负责 `observe → propose → validate → emit` 的 4 Agent stub；Agent 只产生 `AgentAction`，纯函数负责行动效果、状态归并、干预和结局判定；SSE 直接消费引擎的事件迭代器。

**技术栈：** Python 3.12、FastAPI、Pydantic v2、LangGraph、`sse-starlette`、pytest、httpx。MVP-0 使用 `langchain-core` 只保留未来模型适配边界，不安装具体模型供应商 SDK。

## Global Constraints

- MVP-0 只支持 `scenarios/milktea_startup.json` 一个场景，所有场景事实、阈值和行动效果必须来自决策源。
- `app/engine/` 不直接调用 LLM；Agent 调用只发生在 `app/agents/` 的协议边界。
- Agent 不得直接修改 `WorldState`，也不得决定最终 `result`。
- API 请求和响应必须使用 Pydantic 模型，不接受核心流程中的任意 `dict`。
- `use_stub` 由配置和测试依赖注入控制，客户端请求不得切换真实模型。
- SSE 流的是领域事件，不声称提供 LLM token 流。
- MVP-0 不引入 SQLAlchemy、SQLite、PostgreSQL、pgvector、Chroma、Redis、Alembic、MCP 或账号鉴权。
- MVP-0 不实现 LangGraph `interrupt()` 跨请求续推；无干预选择时只返回 `paused` 状态。
- 代码与 JSON 字段使用 `snake_case`；中文只出现在展示文案和场景内容中。
- 不在本计划中执行 `git commit` 或 `git push`。

## 文件结构

**创建：**

- `pyproject.toml`
- `app/__init__.py`
- `app/core/__init__.py`
- `app/core/config.py`
- `app/core/errors.py`
- `app/schemas/__init__.py`
- `app/schemas/decision_source.py`
- `app/schemas/api.py`
- `app/schemas/events.py`
- `app/scenarios/__init__.py`
- `app/scenarios/loader.py`
- `app/engine/__init__.py`
- `app/engine/models.py`
- `app/engine/state.py`
- `app/engine/reducers.py`
- `app/engine/ending.py`
- `app/engine/interventions.py`
- `app/engine/scoring.py`
- `app/engine/compare.py`
- `app/engine/nodes.py`
- `app/engine/graph.py`
- `app/engine/engine.py`
- `app/agents/__init__.py`
- `app/agents/base.py`
- `app/agents/contracts.py`
- `app/agents/market.py`
- `app/agents/environment.py`
- `app/agents/personal.py`
- `app/agents/risk.py`
- `app/agents/inner_graph.py`
- `app/api/__init__.py`
- `app/api/dependencies.py`
- `app/api/simulation.py`
- `app/api/stream.py`
- `app/main.py`
- `scenarios/milktea_startup.json`
- `tests/conftest.py`
- `tests/test_config_and_loader.py`
- `tests/test_decision_source.py`
- `tests/test_state_and_reducers.py`
- `tests/test_agents_stub.py`
- `tests/test_graph_and_engine.py`
- `tests/test_interventions.py`
- `tests/test_scoring_and_compare.py`
- `tests/test_api.py`
- `tests/test_stream.py`
- `tests/test_e2e_milktea.py`

**明确不创建：**

- `app/db/`
- `alembic.ini`
- `app/kb/`
- `app/mcp_server/`
- 真实模型 provider 文件

---

### Task 1: 项目骨架、配置和安全的场景加载

**Files:**

- Create: `pyproject.toml`
- Create: `app/core/config.py`
- Create: `app/core/errors.py`
- Create: `app/scenarios/loader.py`
- Create: `tests/conftest.py`
- Test: `tests/test_config_and_loader.py`

**Interfaces:**

- Produces `Settings`, `ScenarioLoader`, `ScenarioNotFoundError`, `InvalidScenarioIdError` and `ScenarioIdMismatchError`.
- 后续任务通过 `ScenarioLoader.load("milktea_startup")` 获取已校验的 `DecisionSource`。

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config_and_loader.py
import json
from pathlib import Path
import re

import pytest

from app.core.errors import (
    InvalidScenarioIdError,
    ScenarioIdMismatchError,
    ScenarioNotFoundError,
)
from app.scenarios.loader import ScenarioLoader


def test_loader_reads_scenario_from_configured_root(tmp_path: Path):
    payload = {
        "scenario_id": "demo",
        "title": "Demo",
        "version": 1,
        "decision_vars": [
            {
                "name": "budget",
                "value_type": "integer",
                "required": True,
                "default": 200000,
            }
        ],
        "initial_world_state": {},
        "agents": [
            {
                "agent_id": agent_id,
                "name": agent_id,
                "stance": "test",
                "goal": "test",
                "action_ids": [f"{agent_id}.hold"],
            }
            for agent_id in ("market", "environment", "personal", "risk")
        ],
        "action_effects": [
            {
                "action_id": "market.hold",
                "effects": {},
                "reason_template": "test",
            }
        ],
        "intervention_effects": [],
        "end_conditions": {
            "bankrupt": {"metric": "cash_flow", "op": "<=", "threshold": 0},
            "goal_reached": None,
            "steady_state": None,
            "timeout_years": 1,
        },
        "intervention_rules": [],
    }
    (tmp_path / "demo.json").write_text(json.dumps(payload), encoding="utf-8")

    source = ScenarioLoader(tmp_path).load("demo")

    assert source.scenario_id == "demo"


def test_loader_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(InvalidScenarioIdError):
        ScenarioLoader(tmp_path).load("../demo")


def test_loader_reports_missing_scenario(tmp_path: Path):
    with pytest.raises(ScenarioNotFoundError):
        ScenarioLoader(tmp_path).load("missing")


def test_loader_rejects_filename_and_payload_id_mismatch(tmp_path: Path):
    (tmp_path / "demo.json").write_text(
        json.dumps({"scenario_id": "other"}),
        encoding="utf-8",
    )
    with pytest.raises(ScenarioIdMismatchError):
        ScenarioLoader(tmp_path).load("demo")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_and_loader.py -v`

Expected: FAIL because the configuration, errors, loader and schemas do not exist.

- [ ] **Step 3: Write the minimal implementation**

`pyproject.toml` must contain only the MVP-0 runtime dependencies:

```toml
[project]
name = "yanjie-ai"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.30,<1",
    "pydantic>=2.9,<3",
    "langgraph>=0.2,<1",
    "langchain-core>=0.3,<1",
    "sse-starlette>=2.1,<3",
]

[project.optional-dependencies]
dev = [
    "httpx>=0.27,<1",
    "pytest>=8.3,<9",
    "pytest-asyncio>=0.24,<1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

`app/core/config.py` must expose a deterministic settings object:

```python
from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    scenario_dir: Path
    llm_use_stub: bool = True
    max_years: int = 10
    max_interventions: int = 3


def get_settings() -> Settings:
    return Settings(
        scenario_dir=Path(os.getenv("SCENARIO_DIR", "scenarios")).resolve(),
        llm_use_stub=os.getenv("LLM_USE_STUB", "1") == "1",
        max_years=int(os.getenv("MAX_YEARS", "10")),
        max_interventions=int(os.getenv("MAX_INTERVENTIONS", "3")),
    )
```

Task 1 creates a temporary `DecisionSource` loader shim so the loader can be tested in isolation. Task 2 replaces that shim with the strict domain schema. The Task 1 fixture already uses the Task 2 field shape so the tests remain valid across that replacement.

`app/scenarios/loader.py` must validate a lowercase snake_case identifier before resolving the path and reject a JSON payload whose `scenario_id` differs from the filename:

```python
import json
from pathlib import Path

from app.core.errors import (
    InvalidScenarioIdError,
    ScenarioIdMismatchError,
    ScenarioNotFoundError,
)
from app.schemas.decision_source import DecisionSource


_SCENARIO_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class ScenarioLoader:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self._cache: dict[str, DecisionSource] = {}

    def load(self, scenario_id: str) -> DecisionSource:
        if not isinstance(scenario_id, str) or not _SCENARIO_ID_PATTERN.fullmatch(
            scenario_id
        ):
            raise InvalidScenarioIdError(scenario_id)
        if scenario_id in self._cache:
            return self._cache[scenario_id]
        path = (self.root / f"{scenario_id}.json").resolve()
        if path.parent != self.root or not path.is_file():
            raise ScenarioNotFoundError(scenario_id)
        source = DecisionSource.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        if source.scenario_id != scenario_id:
            raise ScenarioIdMismatchError(scenario_id, source.scenario_id)
        self._cache[scenario_id] = source
        return source
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config_and_loader.py -v`

Expected: PASS.

- [ ] **Step 5: Run dependency and import verification**

Run: `python -m pip install -e ".[dev]"`
Run: `python -c "import fastapi, langgraph, pydantic, sse_starlette"`

Expected: both commands exit with code 0.

---

### Task 2: Typed decision source and the first scenario

**Files:**

- Create: `app/schemas/decision_source.py`
- Create: `scenarios/milktea_startup.json`
- Test: `tests/test_decision_source.py`

**Interfaces:**

- Produces `DecisionSource`, `DecisionVarDef`, `AgentDef`, `ActionEffectDef`, `EndConditions` and `InterventionRule`.
- All metric names are stable snake_case identifiers: `cash_flow`, `customer_flow`, `competition_count`, `monthly_profit`, `payback_ratio`.
- Later reducers consume `ActionEffectDef.effects` and never hard-code business deltas.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_decision_source.py
from app.scenarios.loader import ScenarioLoader


def test_milktea_source_is_typed_and_complete():
    source = ScenarioLoader("scenarios").load("milktea_startup")

    assert source.scenario_id == "milktea_startup"
    assert {agent.agent_id for agent in source.agents} == {
        "market",
        "environment",
        "personal",
        "risk",
    }
    assert source.end_conditions.bankrupt.metric == "cash_flow"
    assert source.end_conditions.timeout_years == 3
    assert source.intervention_rules[0].max_uses == 1
    assert any(effect.action_id == "market.differentiate"
               for effect in source.action_effects)


def test_source_rejects_unknown_operator():
    from pydantic import ValidationError
    from app.schemas.decision_source import InterventionRule

    try:
        InterventionRule(
            rule_id="bad",
            metric="cash_flow",
            operator="between",
            threshold=1,
            event="bad",
            options=["a"],
        )
    except ValidationError:
        return
    raise AssertionError("unknown operator must be rejected")
```

- [ ] **Step 2: Run the focused tests**

Run: `pytest tests/test_decision_source.py -v`

Expected: FAIL because the typed models and fixture do not exist.

- [ ] **Step 3: Implement the typed models**

Use `Literal` for finite operators and variable types. Use `Field(default_factory=...)` for all list and dict defaults. Do not use `dict = {}` or `list = []`.

The essential model shape is:

```python
from typing import Any, Literal
from pydantic import BaseModel, Field


class DecisionVarDef(BaseModel):
    name: str
    value_type: Literal["integer", "number", "string"]
    required: bool = True
    default: Any = None
    minimum: float | None = None
    maximum: float | None = None


class AgentDef(BaseModel):
    agent_id: Literal["market", "environment", "personal", "risk"]
    name: str
    stance: str
    goal: str
    action_ids: list[str] = Field(min_length=1)


class ActionEffectDef(BaseModel):
    action_id: str
    effects: dict[str, float] = Field(default_factory=dict)
    reason_template: str


class MetricCondition(BaseModel):
    metric: str
    operator: Literal["<", "<=", ">", ">=", "=="]
    threshold: float


class EndConditions(BaseModel):
    bankrupt: MetricCondition
    goal_reached: MetricCondition | None = None
    steady_state: MetricCondition | None = None
    timeout_years: int = Field(gt=0, le=10)


class InterventionRule(BaseModel):
    rule_id: str
    metric: str
    operator: Literal["<", "<=", ">", ">=", "=="]
    threshold: float
    event: str
    options: list[str] = Field(min_length=1)
    max_uses: int = Field(default=1, ge=1)


class DecisionSource(BaseModel):
    scenario_id: str
    title: str
    version: int = Field(ge=1)
    decision_vars: list[DecisionVarDef] = Field(min_length=1)
    initial_world_state: dict[str, float] = Field(default_factory=dict)
    agents: list[AgentDef] = Field(min_length=4, max_length=4)
    action_effects: list[ActionEffectDef] = Field(min_length=1)
    intervention_effects: list[ActionEffectDef] = Field(default_factory=list)
    end_conditions: EndConditions
    intervention_rules: list[InterventionRule] = Field(default_factory=list)
```

- [ ] **Step 4: Write the scenario JSON**

The fixture must include:

- default budget `200000`, city `"hangzhou"`, industry `"milk_tea"`, span `3`;
- initial cash flow `200000`, customer flow `100`, competition count `47`, monthly profit `0`, payback ratio `0`;
- four agents and at least one valid action per agent;
- action effects for every referenced action;
- bankruptcy at `cash_flow <= 0`;
- at least two intervention rules;
- `max_uses` values that can be tested independently.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_decision_source.py -v`

Expected: PASS.

---

### Task 3: State models, deterministic reducers and ending rules

**Files:**

- Create: `app/engine/models.py`
- Create: `app/engine/state.py`
- Create: `app/engine/reducers.py`
- Create: `app/engine/ending.py`
- Test: `tests/test_state_and_reducers.py`

**Interfaces:**

- Produces `WorldState`, `AgentAction`, `StateEffect`, `TimelineNode`, `SimulationState`, `TransitionResult` and `EndingResult`.
- Produces pure functions `make_initial_state`, `apply_actions`, `judge_ending` and `append_timeline`.
- `apply_actions` and `judge_ending` accept `WorldState | Mapping[str, float]` and normalize to `WorldState` at the boundary.
- `apply_actions` is the only place where action effects change the world.

- [ ] **Step 1: Write failing tests for state invariants**

```python
# tests/test_state_and_reducers.py
from app.engine.ending import judge_ending
from app.engine.reducers import apply_actions
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader
from app.engine.models import AgentAction


def test_initial_state_uses_source_defaults():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(
        source,
        {"budget": 200000, "city": "hangzhou", "industry": "milk_tea", "span_years": 3},
    )

    assert state.year == 0
    assert state.phase == "input"
    assert state.world_state.cash_flow == 200000
    assert state.timeline == []


def test_apply_actions_is_deterministic_and_records_effects():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    initial = make_initial_state(source, {"budget": 200000})
    actions = [
        AgentAction(
            agent_id="market",
            action_id="market.differentiate",
            reason="test",
            confidence=1.0,
        )
    ]

    result = apply_actions(initial.world_state, actions, source)

    assert result.world_state.cash_flow != initial.world_state.cash_flow
    assert result.effects[0].action_id == "market.differentiate"
    assert result.events[0].agent_id == "market"


def test_bankruptcy_is_pure_rule_based():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    ending = judge_ending(
        world_state={"cash_flow": 0, "customer_flow": 0, "competition_count": 47,
                     "monthly_profit": -1000, "payback_ratio": 0},
        year=1,
        end_conditions=source.end_conditions,
    )

    assert ending.result == "bankrupt"
    assert ending.reason.metric == "cash_flow"
```

- [ ] **Step 2: Run the focused tests**

Run: `pytest tests/test_state_and_reducers.py -v`

Expected: FAIL because the models and pure functions do not exist.

- [ ] **Step 3: Implement immutable domain models**

Use Pydantic models with `model_copy(deep=True)` inside reducers. `SimulationState` must include `scenario_id`, `decision_vars`, `user_profile`, `phase`, `year`, `world_state`, `agent_actions`, `timeline`, `interventions`, `pending_intervention`, `result`, `score`, `score_detail`, `risks` and `action_plan`.

Use typed enums for `phase` (`input`, `simulating`, `paused`, `scoring`, `completed`) and `result` (`goal_reached`, `steady`, `bankrupt`, `timeout`, `paused`).

`WorldState` must explicitly define `cash_flow`, `customer_flow`, `competition_count`, `monthly_profit` and `payback_ratio`. Reducers may update only these declared fields; unknown metrics are a `ValueError`.

- [ ] **Step 4: Implement the reducer contract**

```python
def apply_actions(
    world_state: WorldState | Mapping[str, float],
    actions: list[AgentAction],
    source: DecisionSource,
) -> TransitionResult:
    next_state = WorldState.model_validate(world_state).model_copy(deep=True)
    effects: list[StateEffect] = []
    events: list[EventRecord] = []
    effect_by_action = {item.action_id: item for item in source.action_effects}

    for action in actions:
        definition = effect_by_action[action.action_id]
        for metric, delta in definition.effects.items():
            if not hasattr(next_state, metric):
                raise ValueError(f"unknown world-state metric: {metric}")
            setattr(next_state, metric, getattr(next_state, metric) + delta)
        effects.append(
            StateEffect(action_id=action.action_id, effects=definition.effects)
        )
        events.append(
            EventRecord(
                agent_id=action.agent_id,
                action_id=action.action_id,
                reason=action.reason,
                state_diff=definition.effects,
            )
        )
    return TransitionResult(
        world_state=WorldState.model_validate(next_state),
        effects=effects,
        events=events,
    )
```

The implementation must reject an action that is not declared for its Agent and must never silently invent a metric.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_state_and_reducers.py -v`

Expected: PASS.

---

### Task 4: Agent protocol, four stub Agents and inner coordinator

**Files:**

- Create: `app/agents/contracts.py`
- Create: `app/agents/base.py`
- Create: `app/agents/market.py`
- Create: `app/agents/environment.py`
- Create: `app/agents/personal.py`
- Create: `app/agents/risk.py`
- Create: `app/agents/inner_graph.py`
- Test: `tests/test_agents_stub.py`

**Interfaces:**

- Produces `AgentContext`, `AgentProtocol`, `StubAgent`, `build_agents` and `AgentCoordinator`.
- `AgentCoordinator.propose(state: SimulationState) -> list[AgentAction]`.
- Agent output is validated against the source before it reaches the engine.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_agents_stub.py
from app.agents.inner_graph import AgentCoordinator, build_agents
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader


def test_build_agents_returns_exactly_four_declared_agents():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    agents = build_agents(source, use_stub=True)
    assert set(agents) == {"market", "environment", "personal", "risk"}


def test_stub_actions_are_declared_and_stable():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = make_initial_state(source, {"budget": 200000})
    coordinator = AgentCoordinator(build_agents(source, use_stub=True))

    actions_a = coordinator.propose(state)
    actions_b = coordinator.propose(state)

    assert [item.action_id for item in actions_a] == [item.action_id for item in actions_b]
    assert {item.agent_id for item in actions_a} == {
        "market", "environment", "personal", "risk"
    }
    assert all(item.reason for item in actions_a)
```

- [ ] **Step 2: Run the focused tests**

Run: `pytest tests/test_agents_stub.py -v`

Expected: FAIL because the Agent protocol and coordinator do not exist.

- [ ] **Step 3: Implement the protocol boundary**

```python
from dataclasses import dataclass
from typing import Protocol

from app.engine.models import AgentAction


@dataclass(frozen=True)
class AgentContext:
    agent_id: str
    year: int
    world_state: dict[str, float]
    decision_vars: dict[str, object]
    allowed_action_ids: tuple[str, ...]


class AgentProtocol(Protocol):
    agent_id: str

    def propose(self, context: AgentContext) -> AgentAction:
        ...
```

`StubAgent` must choose the first allowed action using a deterministic rule based on `agent_id` and current year. It must never emit an undeclared action. The four concrete Agent classes only bind stable IDs and display metadata; they must not contain business state transitions.

- [ ] **Step 4: Implement the inner coordinator**

The coordinator must expose four explicit phases as methods:

```python
class AgentCoordinator:
    def observe(self, state) -> dict[str, AgentContext]: ...
    def propose_actions(self, contexts) -> list[AgentAction]: ...
    def validate(self, actions, contexts) -> list[AgentAction]: ...
    def emit(self, actions) -> list[AgentAction]: ...

    def propose(self, state):
        contexts = self.observe(state)
        return self.emit(self.validate(self.propose_actions(contexts), contexts))
```

`propose()` composes those phases. Validation must check Agent ID, action ID and non-empty reason. It may replace invalid stub output with the first valid declared action, but it must record a validation warning for tests and logs.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_agents_stub.py -v`

Expected: PASS.

---

### Task 5: Outer graph and incremental simulation engine

**Files:**

- Create: `app/engine/graph.py`
- Create: `app/engine/nodes.py`
- Create: `app/engine/engine.py`
- Test: `tests/test_graph_and_engine.py`

**Interfaces:**

- Produces `SimulationEngine.run`, `SimulationEngine.iter_events`, `SimulationEngine.aiter_events`.
- Produces `build_outer_graph(source)`.
- Outer graph nodes remain pure: prepare state, apply supplied actions, check intervention, check ending, append timeline and finalize.
- Agent coordination happens in the engine boundary before the pure transition node; no LLM call is placed inside `app/engine/nodes.py` because this MVP-0 intentionally has no impure engine nodes.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_graph_and_engine.py
from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader


def test_engine_completes_with_stub_without_external_services():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = SimulationEngine(source, use_stub=True).run({"budget": 200000})

    assert state.phase == "completed"
    assert state.result in {"goal_reached", "steady", "bankrupt", "timeout"}
    assert state.year >= 1
    assert len(state.timeline) >= 1
    assert all(node.agent_actions for node in state.timeline)


def test_engine_respects_source_timeout_and_step_guard():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = SimulationEngine(source, use_stub=True).run(
        {"budget": 200000, "span_years": 3}
    )
    assert state.year <= source.end_conditions.timeout_years
```

- [ ] **Step 2: Run the focused tests**

Run: `pytest tests/test_graph_and_engine.py -v`

Expected: FAIL because the outer graph and engine do not exist.

- [ ] **Step 3: Implement the explicit engine loop**

The engine must use a bounded loop with `max_years = min(requested_span, source.timeout_years, settings.max_years)`. It must raise a domain error if the bound is non-positive, rather than relying on LangGraph recursion limits.

The per-year sequence is:

```python
for year in range(1, max_years + 1):
    contexts = coordinator.observe(state)
    actions = coordinator.emit(coordinator.validate(
        coordinator.propose(contexts), contexts
    ))
    state = graph.invoke({"state": state, "actions": actions})
    yield year_completed_event(state)
    if state.phase in {"paused", "completed"}:
        break
```

The graph invocation must not mutate the input state object. Each timeline node must include `year`, `world_state`, `agent_actions`, `state_diff`, `interventions` and `ending`.

- [ ] **Step 4: Implement event iteration**

`iter_events()` must yield `simulation.started` before the first year, one `year.completed` after each committed year, `intervention.pending` when no choice is available, and exactly one terminal event:

- `simulation.completed` for a completed result;
- `simulation.paused` for a pending intervention;
- `simulation.failed` for a normalized domain failure.

Every event must include a monotonic integer `sequence`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_graph_and_engine.py -v`

Expected: PASS.

---

### Task 6: Deterministic interventions and bounded ending logic

**Files:**

- Create: `app/engine/interventions.py`
- Modify: `app/engine/engine.py`
- Modify: `app/engine/state.py`
- Test: `tests/test_interventions.py`

**Interfaces:**

- Produces `find_pending_intervention`, `apply_intervention` and `validate_intervention_choice`.
- `SimulationEngine.run(..., intervention_choices: dict[int, str] | None = None)` accepts choices keyed by year.
- A missing choice returns `phase="paused"` with `pending_intervention`; it does not silently choose a default.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_interventions.py
from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader


def test_missing_intervention_choice_pauses_simulation():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = SimulationEngine(source, use_stub=True).run({"budget": 60000})
    assert state.phase == "paused"
    assert state.pending_intervention is not None


def test_explicit_intervention_choice_changes_state_and_is_recorded():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = SimulationEngine(source, use_stub=True).run(
        {"budget": 60000},
        intervention_choices={1: "cut_costs"},
    )
    assert all(item.choice == "cut_costs" for item in state.interventions)
    assert state.phase == "completed"


def test_invalid_intervention_choice_is_rejected():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)
    try:
        engine.run({"budget": 60000}, intervention_choices={1: "not_declared"})
    except ValueError:
        return
    raise AssertionError("undeclared intervention choice must fail")
```

- [ ] **Step 2: Run the focused tests**

Run: `pytest tests/test_interventions.py -v`

Expected: FAIL because intervention detection and application do not exist.

- [ ] **Step 3: Implement rule evaluation**

Use the same typed operator evaluator for end conditions and intervention rules. Track uses by `rule_id`, enforce each rule's `max_uses`, and enforce the source/session maximum. A rule must return a typed `PendingIntervention` containing `rule_id`, `year`, `event`, `options` and `metric_snapshot`.

- [ ] **Step 4: Implement deterministic option effects**

Intervention effects must be declared in the scenario source through `intervention_effects` action IDs. Do not add code such as `if chosen == "cut_costs": cash += 40000` without a source declaration.

The engine must apply the chosen option through the same reducer used by Agent actions, append an `InterventionRecord`, clear `pending_intervention`, and continue only when the choice is valid.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_interventions.py -v`

Expected: PASS.

---

### Task 7: Scoring, risk extraction and A/B comparison

**Files:**

- Create: `app/engine/scoring.py`
- Create: `app/engine/compare.py`
- Modify: `app/engine/engine.py`
- Test: `tests/test_scoring_and_compare.py`

**Interfaces:**

- Produces pure functions `compute_score`, `extract_risks`, `build_action_plan` and `compare_states`.
- All outputs use typed Pydantic models or typed return tuples.
- Action-plan items contain a concrete action, measurable quantity and deadline.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scoring_and_compare.py
from app.engine.compare import compare_states
from app.engine.scoring import build_action_plan, compute_score, extract_risks


def test_score_is_bounded_and_dimensioned():
    score = compute_score(
        world_state={
            "cash_flow": 100000,
            "customer_flow": 100,
            "competition_count": 50,
            "monthly_profit": 30000,
            "payback_ratio": 0.8,
        },
        result="steady",
    )
    assert 0 <= score.total <= 100
    assert {"market", "resource", "profitability", "risk"} <= set(score.detail)


def test_risk_and_action_plan_are_specific():
    risks = extract_risks(
        {"cash_flow": 20000, "competition_count": 70,
         "customer_flow": 20, "monthly_profit": -1000, "payback_ratio": 0}
    )
    plan = build_action_plan(risks)
    assert any(item.metric == "cash_flow" for item in risks)
    assert len(plan) >= 5
    assert all(item.quantity and item.deadline for item in plan)


def test_compare_contains_stable_dimensions():
    result = compare_states(
        {"cash_flow": 100000, "monthly_profit": 30000},
        "steady",
        {"cash_flow": 50000, "monthly_profit": 10000},
        "timeout",
    )
    assert set(result) == {"assets", "risk", "growth", "pressure", "ending"}
    assert result["ending"]["a"] == "steady"
```

- [ ] **Step 2: Run the focused tests**

Run: `pytest tests/test_scoring_and_compare.py -v`

Expected: FAIL because scoring and comparison functions do not exist.

- [ ] **Step 3: Implement pure scoring**

Use clamped numeric formulas with named dimensions. Do not call an LLM, read environment variables or mutate state. `build_action_plan` must use templates keyed by risk metric and must not contain vague verbs without a number and deadline.

- [ ] **Step 4: Add engine finalization**

When the engine reaches a terminal ending, calculate score, risks and action plan exactly once. A paused state must not be scored as completed. `compare_states` must compare the final snapshots and must not rerun either simulation.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_scoring_and_compare.py -v`

Expected: PASS.

---

### Task 8: Typed FastAPI contracts and synchronous endpoints

**Files:**

- Create: `app/schemas/api.py`
- Create: `app/api/dependencies.py`
- Create: `app/api/simulation.py`
- Create: `app/main.py`
- Test: `tests/test_api.py`

**Interfaces:**

- `POST /api/simulations` accepts `SimulationRequest` and returns `SimulationResponse`.
- `POST /api/simulations/compare` accepts `CompareRequest` and returns `CompareResponse`.
- Scenario loading, configuration and engine construction are dependency-injected for tests.
- The request body has no `use_stub` field.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api.py
from fastapi.testclient import TestClient
from app.main import app


def test_create_simulation_returns_typed_result():
    client = TestClient(app)
    response = client.post(
        "/api/simulations",
        json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 200000},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_id"] == "milktea_startup"
    assert body["result"] in {"goal_reached", "steady", "bankrupt", "timeout"}
    assert body["timeline"]


def test_unknown_scenario_is_not_a_500():
    client = TestClient(app)
    response = client.post(
        "/api/simulations",
        json={"scenario_id": "missing", "decision_vars": {"budget": 1}},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "SCENARIO_NOT_FOUND"


def test_invalid_decision_vars_are_rejected():
    client = TestClient(app)
    response = client.post(
        "/api/simulations",
        json={"scenario_id": "milktea_startup", "decision_vars": {"budget": -1}},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run the focused tests**

Run: `pytest tests/test_api.py -v`

Expected: FAIL because the request/response models and routes do not exist.

- [ ] **Step 3: Implement request and response models**

`SimulationRequest` must contain `scenario_id`, `decision_vars`, optional `user_profile` and optional `intervention_choices`. `SimulationResponse` must contain `session_id`, `scenario_id`, `phase`, `year`, `result`, `timeline`, `score`, `score_detail`, `risks`, `action_plan` and `pending_intervention`.

Use `extra="forbid"` on request models so misspelled fields fail fast.

- [ ] **Step 4: Implement normalized error handling**

Map domain errors to stable JSON:

```json
{
  "code": "SCENARIO_NOT_FOUND",
  "message": "场景不存在",
  "request_id": "..."
}
```

Do not return raw tracebacks, filesystem paths or model-provider errors.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`

Expected: PASS.

---

### Task 9: Event schema and real incremental SSE

**Files:**

- Create: `app/schemas/events.py`
- Create: `app/api/stream.py`
- Modify: `app/main.py`
- Modify: `app/engine/engine.py`
- Test: `tests/test_stream.py`

**Interfaces:**

- `POST /api/simulations/stream` returns `EventSourceResponse`.
- Event names are `simulation.started`, `year.completed`, `intervention.pending`, `simulation.completed`, `simulation.paused` and `simulation.failed`.
- Every event has `sequence`, `session_id`, `scenario_id`, `event_type` and typed `payload`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_stream.py
import json
from fastapi.testclient import TestClient
from app.main import app


def _events(response):
    current = {}
    for line in response.iter_lines():
        if not line:
            if current:
                yield current
                current = {}
            continue
        if line.startswith("event:"):
            current["event"] = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line.removeprefix("data:").strip())


def test_stream_is_incremental_and_has_one_terminal_event():
    client = TestClient(app)
    with client.stream(
        "POST",
        "/api/simulations/stream",
        json={
            "scenario_id": "milktea_startup",
            "decision_vars": {"budget": 200000},
        },
    ) as response:
        assert response.status_code == 200
        events = list(_events(response))

    names = [item["event"] for item in events]
    assert names[0] == "simulation.started"
    assert "year.completed" in names
    assert names[-1] in {"simulation.completed", "simulation.paused"}
    assert sum(name in {"simulation.completed", "simulation.paused",
                        "simulation.failed"} for name in names) == 1
    assert [item["data"]["sequence"] for item in events] == list(range(len(events)))
```

- [ ] **Step 2: Run the focused test**

Run: `pytest tests/test_stream.py -v`

Expected: FAIL because the stream route and event schema do not exist.

- [ ] **Step 3: Implement event envelopes**

Use a Pydantic `SimulationEvent` with an enum event type and a typed payload union. The JSON `data` field must contain one serialized event payload; do not serialize the entire internal `SimulationState` into every event.

- [ ] **Step 4: Implement the SSE generator**

The route must:

1. validate the request before opening the stream;
2. construct the engine through dependencies;
3. iterate `engine.aiter_events(...)`;
4. yield `{event: event.event_type, id: str(event.sequence), data: event.model_dump_json()}`;
5. normalize an exception into exactly one `simulation.failed` event.

`aiter_events` may yield control with `await asyncio.sleep(0)` after each domain event in MVP-0. The implementation must not call `engine.run()` first and then loop over a completed timeline.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_stream.py -v`

Expected: PASS.

---

### Task 10: AC7, regression coverage and complete E2E verification

**Files:**

- Create: `tests/test_ac7_decoupling.py`
- Create: `tests/test_e2e_milktea.py`
- Modify: focused test files only when a preceding contract requires an assertion

**Interfaces:**

- Proves outcome decisions are independent of Agent explanation text and model availability.
- Proves parameter changes alter the deterministic path.
- Proves all event and synchronous response contracts work together.

- [ ] **Step 1: Write the AC7 test**

```python
# tests/test_ac7_decoupling.py
from app.engine.ending import judge_ending
from app.engine.engine import SimulationEngine
from app.engine.models import AgentAction
from app.engine.reducers import apply_actions
from app.scenarios.loader import ScenarioLoader


def test_ending_is_independent_of_agent_reason_text():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    world_state = {
        "cash_flow": 100000,
        "customer_flow": 100,
        "competition_count": 47,
        "monthly_profit": 30000,
        "payback_ratio": 0.8,
    }
    actions_a = [AgentAction(
        agent_id="market",
        action_id="market.differentiate",
        reason="短理由",
        confidence=1.0,
    )]
    actions_b = [AgentAction(
        agent_id="market",
        action_id="market.differentiate",
        reason="完全不同的长理由",
        confidence=0.1,
    )]
    next_a = apply_actions(world_state, actions_a, source).world_state
    next_b = apply_actions(world_state, actions_b, source).world_state
    first = judge_ending(
        next_a,
        1,
        source.end_conditions,
    )
    second = judge_ending(
        next_b,
        1,
        source.end_conditions,
    )
    assert first.result == second.result


def test_low_budget_reaches_bankrupt_with_stub_only():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    state = SimulationEngine(source, use_stub=True).run({"budget": 1})
    assert state.result == "bankrupt"
```

- [ ] **Step 2: Write the E2E test**

```python
# tests/test_e2e_milktea.py
from app.engine.engine import SimulationEngine
from app.scenarios.loader import ScenarioLoader


def test_milktea_full_flow_is_replayable():
    source = ScenarioLoader("scenarios").load("milktea_startup")
    engine = SimulationEngine(source, use_stub=True)

    first = engine.run({"budget": 200000, "span_years": 3})
    second = engine.run({"budget": 200000, "span_years": 3})

    assert first.model_dump(exclude={"session_id"}) == second.model_dump(
        exclude={"session_id"}
    )
    assert first.timeline
    assert first.score is not None
    assert first.risks is not None
    assert first.action_plan
```

- [ ] **Step 3: Run focused AC7 and E2E tests**

Run: `pytest tests/test_ac7_decoupling.py tests/test_e2e_milktea.py -v`

Expected: PASS.

- [ ] **Step 4: Run the complete test suite**

Run: `pytest -v`

Expected: all tests PASS without API keys, database services or network access.

- [ ] **Step 5: Run a manual API smoke test**

Run: `uvicorn app.main:app --host 127.0.0.1 --port 8000`
Run in another terminal:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/simulations `
  -ContentType "application/json" `
  -Body '{"scenario_id":"milktea_startup","decision_vars":{"budget":200000}}'
```

Expected: JSON response contains `phase`, `result`, `timeline`, `score`, `risks` and `action_plan`.

## Deferred Follow-up Plans

These items are deliberately outside this plan and must not be smuggled into MVP-0 tasks:

1. **MVP-1 model integration:** provider adapters, system/user prompt separation, protocol-level structured output, retry/timeout/circuit breaker and real Judge validation.
2. **MVP-1 HITL:** LangGraph `interrupt()`, checkpointer, resume endpoint and persistent pending-intervention state.
3. **MVP-1 knowledge grounding:** Chroma, embedding, metadata filters, source citations and RAG retrieval tests.
4. **MVP-2 persistence:** SQLAlchemy repositories, SQLite development database, PostgreSQL migrations, event persistence and replay.
5. **MVP-2 product APIs:** scenario library CRUD, user profiles, long-term Agent memory, authentication and report export.
6. **MVP-2 external tools:** MCP server, tool timeouts, permission boundaries and real market/policy queries.

## Plan Self-Review

### Scope coverage

- Decision-source validation: Task 2.
- Deterministic state transition and AC7: Tasks 3, 5 and 10.
- Four Agents and inner coordination boundary: Task 4.
- Yearly simulation and bounded termination: Task 5.
- Intervention detection and deterministic choices: Task 6.
- Scoring, risks, action plan and comparison: Task 7.
- Typed synchronous API: Task 8.
- Incremental SSE domain events: Task 9.
- Full regression and smoke verification: Task 10.

### Placeholder scan

- No task relies on another document's line numbers.
- No task says “implement later”, “add suitable handling”, “write tests for the above” or “similar to another task”.
- Deferred work is listed only in the explicit follow-up section.

### Type and boundary consistency

- `DecisionSource` is loaded once by `ScenarioLoader` and passed to the engine.
- `AgentAction` is the only Agent output consumed by reducers.
- `SimulationState` is the only engine result consumed by API serializers and event builders.
- `SimulationEngine.run`, `iter_events` and `aiter_events` share the same request arguments.
- `use_stub` is configuration-controlled and absent from API request models.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-30-mvp0-backend.md`. Execute it task-by-task with tests after each task. The current workspace instructions prohibit automatic Git commits and pushes, so commits remain a user-controlled step outside this plan.
