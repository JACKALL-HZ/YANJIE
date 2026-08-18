# MVP-1 LlmAgent 模块实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 将 MVP-0 的 StubAgent 替换为基于 DeepSeek API 的真实 LlmAgent，保持 AgentCoordinator 和内层 LangGraph 零改动。

**架构：** 新增 `LlmAgent` 类实现 `AgentProtocol`，用 `ChatOpenAI` 调 DeepSeek `deepseek-chat`；新增 `build_agent_prompt()` 工厂按 Agent 的 stance/goal/action_descriptions 构建 system+user prompt；`build_agents()` 新增 `use_stub=False` 分支，传入 `fast_llm` + `action_effects` 的 reason_template 映射。

**技术栈：** Python 3.12, LangChain ChatOpenAI, DeepSeek `deepseek-chat`, Pydantic v2, langchain-core prompt templates

---

### 任务 1：创建 LlmAgent 核心类

**文件：**
- 创建：`app/agents/llm_agent.py`
- 创建：`tests/test_agents_llm.py`

- [ ] **步骤 1：编写 LlmAgent 测试（先写测试驱动）**

```python
"""LlmAgent 单元测试 — 仅测 prompt 构建和响应解析，不调真实 API"""

import json
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from app.agents.contracts import AgentContext
from app.agents.llm_agent import LlmAgent
from app.engine.models import AgentAction


def make_context(agent_id="market", year=1, allowed=("market.differentiate", "market.hold")):
    return AgentContext(
        agent_id=agent_id,
        year=year,
        world_state={"cash_flow": 180000, "customer_flow": 100, "competition_count": 47, "monthly_profit": 0, "payback_ratio": 0},
        decision_vars={"budget": 200000, "city": "hangzhou", "industry": "milk_tea"},
        allowed_action_ids=allowed,
    )


def test_llm_agent_parses_valid_json_response():
    """LLM 返回合法 JSON → 正确解析为 AgentAction"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.differentiate", "reason": "need growth"}'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow customers",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate to grow demand",
            "market.hold": "Hold and collect data",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.agent_id == "market"
    assert result.action_id == "market.differentiate"
    assert result.reason == "need growth"
    assert result.confidence == 0.8


def test_llm_agent_rejects_undeclared_action():
    """LLM 返回不在 allowed 里的 action → 降级为第一个 allowed action"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.destroy", "reason": "burn it all"}'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.action_id == "market.differentiate"  # fallback


def test_llm_agent_handles_markdown_wrapped_json():
    """LLM 返回 markdown 包裹的 JSON → 正确提取"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='```json\n{"action_id": "market.hold", "reason": "play safe"}\n```'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.action_id == "market.hold"
    assert result.reason == "play safe"


def test_llm_agent_handles_plain_text_json():
    """LLM 返回带前缀文字的 JSON → 正确提取"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='I choose to differentiate.\n\n{"action_id": "market.differentiate", "reason": "growth needed"}'
    )
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.action_id == "market.differentiate"


def test_llm_agent_fallback_on_garbage():
    """LLM 返回完全不可解析的内容 → fallback 到第一个 allowed action"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="I refuse to choose!")
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    result = agent.propose(make_context())
    assert result.action_id == "market.differentiate"  # fallback
    assert "fallback" in result.reason.lower()


def test_llm_agent_prompt_includes_world_state():
    """验证 prompt 包含世界状态数据"""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content='{"action_id": "market.hold", "reason": "ok"}')
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="customer focused", goal="grow",
        allowed_action_ids=("market.differentiate", "market.hold"),
        action_descriptions={
            "market.differentiate": "Differentiate",
            "market.hold": "Hold",
        },
        llm=mock_llm,
    )
    agent.propose(make_context())
    call_args = mock_llm.invoke.call_args[0][0]
    # 转为字符串检查
    text = str(call_args)
    assert "180000" in text  # cash_flow value
    assert "customer_flow" in text


def test_llm_agent_context_mismatch_raises():
    """context.agent_id 不匹配 → ValueError"""
    mock_llm = MagicMock()
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="x", goal="x",
        allowed_action_ids=("market.differentiate",),
        action_descriptions={"market.differentiate": "d"},
        llm=mock_llm,
    )
    ctx = make_context(agent_id="risk")
    try:
        agent.propose(ctx)
        assert False, "should have raised"
    except ValueError as e:
        assert "mismatch" in str(e).lower()


def test_llm_agent_no_allowed_actions_raises():
    """空 allowed_action_ids → ValueError"""
    mock_llm = MagicMock()
    agent = LlmAgent(
        agent_id="market", name="Market Agent",
        stance="x", goal="x",
        allowed_action_ids=(),
        action_descriptions={},
        llm=mock_llm,
    )
    ctx = make_context(allowed=())
    try:
        agent.propose(ctx)
        assert False, "should have raised"
    except ValueError as e:
        assert "no allowed" in str(e).lower()
```

- [ ] **步骤 2：运行测试确认失败**

```bash
cd "E:\衍界 YANJIE" && C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pytest tests/test_agents_llm.py -v
```
预期：全部 FAIL，`ModuleNotFoundError: No module named 'app.agents.llm_agent'`

- [ ] **步骤 3：实现 LlmAgent 类**

```python
"""LlmAgent：基于 ChatOpenAI 的决策 Agent，替代 StubAgent。"""

import json
import re

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.contracts import AgentContext
from app.engine.models import AgentAction


_SYSTEM_PROMPT = """You are {name}, a decision agent in a business simulation. Your role is {agent_id}.

Your stance: {stance}
Your goal: {goal}

You must choose exactly ONE action from the allowed list below. Evaluate the current world state against your goal, then pick the action that best advances your position.

Respond with a JSON object containing exactly two fields:
- "action_id": one of the allowed action IDs
- "reason": a brief explanation (one sentence) of why you chose this action

No other text. JSON only."""


_USER_PROMPT = """Year: {year}
Decision Variables: {decision_vars_json}

Current World State:
{world_state_json}

Allowed Actions:
{allowed_actions_text}

Choose one action:"""


def _json_from_text(text: str) -> dict | None:
    """从 LLM 响应中提取 JSON 对象。

    处理三种常见格式：
    1. 纯 JSON 字符串
    2. markdown 代码块包裹的 JSON
    3. 文本中嵌入的 JSON 对象
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
    # 尝试提取任意 JSON 对象
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
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
        return self._parse(response.content, allowed)

    def _build_messages(self, context: AgentContext) -> list:
        action_lines = []
        for aid in context.allowed_action_ids:
            desc = self.action_descriptions.get(aid, "(no description)")
            action_lines.append(f"- {aid}: {desc}")

        system = SystemMessage(content=_SYSTEM_PROMPT.format(
            name=self.name,
            agent_id=self.agent_id,
            stance=self.stance,
            goal=self.goal,
        ))
        user = HumanMessage(content=_USER_PROMPT.format(
            year=context.year,
            decision_vars_json=json.dumps(context.decision_vars, ensure_ascii=False),
            world_state_json=json.dumps(context.world_state, ensure_ascii=False, indent=2),
            allowed_actions_text="\n".join(action_lines),
        ))
        return [system, user]

    def _parse(self, content: str, allowed: tuple[str, ...]) -> AgentAction:
        data = _json_from_text(content)
        if data is None:
            # 完全不可解析：fallback
            return AgentAction(
                agent_id=self.agent_id,
                action_id=allowed[0],
                reason=f"LLM response unparseable, fallback to {allowed[0]}: {content[:80]}",
                confidence=0.2,
            )

        action_id = str(data.get("action_id", "")).strip()
        reason = str(data.get("reason", "")).strip() or "llm proposed"

        if action_id not in allowed:
            fallback = allowed[0]
            reason = f"LLM proposed '{action_id}' (undeclared), fallback to {fallback}. {reason}"
            action_id = fallback
            confidence = 0.3
        else:
            confidence = 0.8

        return AgentAction(
            agent_id=self.agent_id,
            action_id=action_id,
            reason=reason,
            confidence=confidence,
        )
```

- [ ] **步骤 4：运行 LlmAgent 单元测试确认通过**

```bash
cd "E:\衍界 YANJIE" && C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pytest tests/test_agents_llm.py -v
```
预期：8 passed

- [ ] **步骤 5：Commit**

```bash
git add app/agents/llm_agent.py tests/test_agents_llm.py
git commit -m "Add LlmAgent with prompt-driven decision making"
```

---

### 任务 2：更新 build_agents 支持 LlmAgent 模式

**文件：**
- 修改：`app/agents/inner_graph.py`

- [ ] **步骤 1：修改 build_agents 的 use_stub=False 分支**

将第 59-60 行的 `raise RuntimeError("MVP-0 only supports stub agents")` 替换为真实 LlmAgent 构建逻辑。

完整修改后的 `build_agents`：

```python
def build_agents(
    source: DecisionSource,
    use_stub: bool = True,
    fast_llm: "BaseChatModel | None" = None,
) -> dict[str, AgentProtocol]:
    declared = {agent.agent_id: agent for agent in source.agents}
    expected = {"market", "environment", "personal", "risk"}
    if set(declared) != expected:
        raise ValueError("source must declare exactly four supported agents")

    # 构建 action_id → reason_template 映射（给 LlmAgent 用）
    action_descriptions: dict[str, str] = {
        effect.action_id: effect.reason_template
        for effect in source.action_effects
    }

    if use_stub:
        agents: dict[str, AgentProtocol] = {
            "market": MarketAgent(),
            "environment": EnvironmentAgent(),
            "personal": PersonalAgent(),
            "risk": RiskAgent(),
        }
        for agent_id, agent in agents.items():
            if not declared[agent_id].action_ids:
                raise ValueError(f"agent has no declared actions: {agent_id}")
            setattr(agent, "allowed_action_ids", tuple(declared[agent_id].action_ids))
        return agents

    # --- LLM 模式 ---
    if fast_llm is None:
        raise ValueError("fast_llm is required when use_stub=False")

    agents: dict[str, AgentProtocol] = {}
    for agent_def in source.agents:
        allowed = tuple(agent_def.action_ids)
        if not allowed:
            raise ValueError(f"agent has no declared actions: {agent_def.agent_id}")
        agent = LlmAgent(
            agent_id=agent_def.agent_id,
            name=agent_def.name,
            stance=agent_def.stance,
            goal=agent_def.goal,
            allowed_action_ids=allowed,
            action_descriptions=action_descriptions,
            llm=fast_llm,
        )
        agents[agent_def.agent_id] = agent
    return agents
```

需要新增 import：
```python
from app.agents.llm_agent import LlmAgent
from langchain_core.language_models import BaseChatModel
```

type hint `fast_llm: "BaseChatModel | None"` 用引号避免运行时导入 langchain-core 类型。

- [ ] **步骤 2：运行现有测试确认零回归**

```bash
cd "E:\衍界 YANJIE" && C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pytest tests/ -q --tb=line
```
预期：41 passed（含 test_agents_stub.py 两个 stub 测试）

- [ ] **步骤 3：编写 build_agents LlmAgent 模式测试**

在 `tests/test_agents_llm.py` 末尾追加：

```python
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage

from app.agents.contracts import AgentProtocol
from app.agents.inner_graph import AgentCoordinator, build_agents
from app.agents.llm_agent import LlmAgent
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader


def test_build_agents_with_llm_returns_llm_agents():
    """use_stub=False + mock LLM → 返回 4 个 LlmAgent 实例"""
    source = ScenarioLoader("scenarios").load("milktea_startup")
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content='{"action_id": "market.differentiate", "reason": "test"}'
    )
    agents = build_agents(source, use_stub=False, fast_llm=mock_llm)
    assert set(agents) == {"market", "environment", "personal", "risk"}
    assert all(isinstance(a, LlmAgent) for a in agents.values())
    # 每个 agent 的 llm 应该是同一个 mock
    assert agents["market"].llm is mock_llm


def test_llm_agent_coordinator_integration():
    """LlmAgent 可通过 AgentCoordinator.propose 正常调用"""
    source = ScenarioLoader("scenarios").load("milktea_startup")

    # 每个 agent 的 mock 返回各自合法 action
    mock_llm = MagicMock()
    responses = {
        "market": '{"action_id": "market.differentiate", "reason": "grow"}',
        "environment": '{"action_id": "environment.localize", "reason": "adapt"}',
        "personal": '{"action_id": "personal.stabilize", "reason": "stable"}',
        "risk": '{"action_id": "risk.contain", "reason": "contain"}',
    }

    def side_effect(messages):
        # 从 system message 找 agent_id
        sys_text = str(messages[0].content)
        for aid in responses:
            if aid in sys_text:
                return AIMessage(content=responses[aid])
        return AIMessage(content='{"action_id": "market.hold", "reason": "default"}')

    mock_llm.invoke.side_effect = side_effect

    agents = build_agents(source, use_stub=False, fast_llm=mock_llm)
    coordinator = AgentCoordinator(agents)
    state = make_initial_state(source, {"budget": 200000})
    actions = coordinator.propose(state)

    assert len(actions) == 4
    assert {a.agent_id for a in actions} == {"market", "environment", "personal", "risk"}
    # 确认每个 agent 的 action 都在各自 declared 范围内
    action_map = {a.agent_id: a.action_id for a in actions}
    for agent_def in source.agents:
        assert action_map[agent_def.agent_id] in agent_def.action_ids


def test_build_agents_without_llm_raises():
    """use_stub=False 但不传 fast_llm → ValueError"""
    source = ScenarioLoader("scenarios").load("milktea_startup")
    try:
        build_agents(source, use_stub=False, fast_llm=None)
        assert False, "should have raised"
    except ValueError as e:
        assert "fast_llm" in str(e).lower()
```

- [ ] **步骤 4：运行测试确认新增 3 条通过**

```bash
cd "E:\衍界 YANJIE" && C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pytest tests/test_agents_llm.py -v
```
预期：11 passed（原 8 + 新增 3）

- [ ] **步骤 5：运行全量测试零回归**

```bash
cd "E:\衍界 YANJIE" && C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pytest tests/ -q --tb=line
```
预期：44 passed

- [ ] **步骤 6：Commit**

```bash
git add app/agents/inner_graph.py tests/test_agents_llm.py
git commit -m "Wire build_agents to create LlmAgent when use_stub=False"
```

---

### 任务 3：更新 engine.py 传递 fast_llm

**文件：**
- 修改：`app/engine/engine.py`

- [ ] **步骤 1：修改 SimulationEngine.__init__ 传递 fast_llm**

engine.py 第 49-51 行当前只传 `use_stub`，需加传 `fast_llm`。

修改为：

```python
from app.core.llm import build_llm

# 在 __init__ 中：
fast_llm = build_llm(self.settings.fast_llm) if not self.use_stub else None
self.coordinator = AgentCoordinator(
    build_agents(source, use_stub=self.use_stub, fast_llm=fast_llm)
)
```

完整修改：将第 49-51 行替换为：

```python
        fast_llm = (
            build_llm(self.settings.fast_llm)
            if not self.use_stub
            else None
        )
        self.coordinator = AgentCoordinator(
            build_agents(source, use_stub=self.use_stub, fast_llm=fast_llm)
        )
```

对应 import 新增（第 1-11 行之后，紧接现有 import）：
```python
from app.core.llm import build_llm
```

- [ ] **步骤 2：运行全量测试确认零回归**

```bash
cd "E:\衍界 YANJIE" && C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pytest tests/ -q --tb=line
```
预期：44 passed（stub 模式下 engine 仍传 fast_llm=None，行为不变）

- [ ] **步骤 3：Commit**

```bash
git add app/engine/engine.py
git commit -m "Pass fast_llm from engine into build_agents"
```

---

### 任务 4：真实 API 冒烟测试

**不写测试文件**——跑一次真实 DeepSeek API 推演，验证全链路通。

- [ ] **步骤 1：临时切 stub 模式为 False + 跑一次模拟**

```bash
cd "E:\衍界 YANJIE" && LLM_USE_STUB=0 C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -c "
from app.core.config import get_settings
from app.core.llm import build_llm
from app.agents.inner_graph import build_agents, AgentCoordinator
from app.engine.state import make_initial_state
from app.scenarios.loader import ScenarioLoader
import os

os.environ['LLM_USE_STUB'] = '0'

source = ScenarioLoader('scenarios').load('milktea_startup')
settings = get_settings()
print(f'fast_llm: {settings.fast_llm.model} @ {settings.fast_llm.base_url}')

llm = build_llm(settings.fast_llm)
agents = build_agents(source, use_stub=False, fast_llm=llm)
coordinator = AgentCoordinator(agents)
state = make_initial_state(source, {'budget': 200000})
actions = coordinator.propose(state)

for a in actions:
    print(f'{a.agent_id}: {a.action_id} (confidence={a.confidence}) reason={a.reason[:80]}')
print('=== LlmAgent deepseek API 连通 OK ===')
"
```
预期：4 Agent 各输出一个基于 DeepSeek 的决策，无异常。

- [ ] **步骤 2：恢复 stub 模式确认测试回归**

```bash
cd "E:\衍界 YANJIE" && C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pytest tests/ -q --tb=line
```
预期：44 passed

---

## 自检

**1. 规格覆盖度：**
- LlmAgent 类 ✅（任务 1）
- Prompt 构建（stance/goal/世界状态/决策变量） ✅（任务 1 `_build_messages`）
- 响应解析（JSON/markdown/fallback） ✅（任务 1 `_json_from_text` + `_parse`）
- build_agents stub/llm 双模式 ✅（任务 2）
- engine.py 传递 fast_llm ✅（任务 3）
- 单元测试全覆盖 ✅（任务 1/2，共 14 个测试）
- 真实 API 冒烟 ✅（任务 4）

**2. 占位符扫描：** ✅ 无占位符，所有步骤含完整代码。

**3. 类型一致性：**
- `LlmAgent.agent_id: str` ↔ `build_agents` 传 `agent_def.agent_id: Literal[...]` ✅
- `AgentProtocol.propose(context: AgentContext) -> AgentAction` ↔ `LlmAgent.propose` 签名一致 ✅
- `build_agents(fast_llm: BaseChatModel | None)` ↔ `engine.py` 传 `build_llm(settings.fast_llm)` ✅
- `action_descriptions: dict[str, str]` ↔ 从 `source.action_effects[*].reason_template` 构建 ✅

**边界情况：**
- ❌ 原计划缺失 → T4 冒烟测试确认 4 测试（test_agents_stub.py）仍通过
- ❌ 原计划缺失 → 补充 T5 全量回归测试验证
- ❌ 原计划缺失 → `use_stub=False` 时不传 `fast_llm` 抛 `ValueError` 已覆盖

---

## 风险点（执行时注意）

| 风险 | 缓解 |
|---|---|
| DeepSeek API 可能不按 JSON-only 格式返回 | `_json_from_text` 三重提取策略，fallback 到 allowed[0] |
| `deepseek-chat` temperature=0.7 可能过于随机 | 先保持 0.7，若效果差在 prompt 里加固约束 |
| mock llm 在 integration test 中需要匹配 agent_id | 用 `side_effect` 函数解析 system message 中的 agent name |
