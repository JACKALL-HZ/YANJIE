# 统一推演协议实施计划

> **面向执行智能体：** 必须逐任务执行，并使用测试先行。每个任务的完成都以对应测试通过为准。

**目标：** 让所有场景共享“确认输入 -> 初步分析 -> 第 1 年决策 -> 四方分析/博弈 -> 年度结算 -> 下一年决策”的流程，并使用户事实和个人画像可解释地影响世界状态。

**架构：** 场景 JSON 继续定义数值状态、动作效果和结束条件；新增状态指标声明与画像修正层。API 用 `pause_reason` 明确等待的输入类型，推演引擎据此暂停和恢复。前端仅根据该协议呈现动态指标和对应交互，不再用通用 `paused` 猜测意图。

**技术栈：** Python 3.12、FastAPI、Pydantic、LangGraph、SQLAlchemy、pytest、Vue 3、TypeScript、Pinia。

## 全局约束

- 决策源决定数值状态、动作效果、结束条件和评分；大模型不得直接写入数值结局。
- 所有新增结构化输入输出使用 Pydantic / TypeScript 类型，不以散乱字典穿透核心编排。
- 已持久化的旧会话和旧场景 JSON 必须可读取；新增字段必须提供兼容默认值。
- 画像在创建会话时冻结，后续编辑不得影响该会话。
- 不提交、不推送代码，除非用户明确要求。
- 每个新行为先写失败测试，再写最小实现。

---

## 第一期：统一状态、年度流程与动态起始状态

### 任务 1：声明动态世界状态和画像修正接口

**文件：**

- 修改：`app/schemas/domain_models.py`
- 修改：`app/schemas/decision_source.py`
- 修改：`app/engine/state.py`
- 修改：`app/engine/reducers.py`
- 修改：`app/engine/ending.py`
- 修改：`app/engine/interventions.py`
- 修改：`app/services/scenario_presenter.py`
- 测试：`tests/test_state_and_reducers.py`
- 测试：`tests/test_decision_source.py`

**接口：**

- `StateMetricDef(metric_id, label, unit, initial_value, display_order)`：场景声明的动态指标。
- `WorldState.metrics: dict[str, float]`：保存场景特有指标；现有五个字段继续保留以兼容旧逻辑。
- `ProfileStateModifier(metric, profile_key, multiplier, offset)`：将画像字段映射为初始状态修正。
- `DecisionSource.state_metrics`、`DecisionSource.profile_state_modifiers`：均可选，旧场景使用空列表。
- `make_initial_state(...)`：按“场景默认值 -> 决策变量 -> 画像修正”初始化 `WorldState`。

- [ ] **步骤 1：写失败测试**

```python
def test_profile_and_decision_values_change_declared_initial_metrics():
    source = DecisionSource.model_validate({
        **SOURCE_DATA,
        "state_metrics": [{
            "metric_id": "execution_capacity", "label": "执行能力",
            "unit": "score", "initial_value": 50, "display_order": 1,
        }],
        "profile_state_modifiers": [{
            "metric": "execution_capacity", "profile_key": "weekly_hours",
            "multiplier": 0.5, "offset": 0,
        }],
    })

    state = make_initial_state(
        source, {"budget": 300000}, user_profile={"weekly_hours": 20},
    )

    assert state.world_state.cash_flow == 300000
    assert state.world_state.metrics["execution_capacity"] == 60


def test_legacy_source_keeps_existing_world_state_shape():
    state = make_initial_state(legacy_source, {"budget": 300000})
    assert state.world_state.cash_flow == 300000
    assert state.world_state.metrics == {}
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`pytest tests/test_state_and_reducers.py::test_profile_and_decision_values_change_declared_initial_metrics tests/test_state_and_reducers.py::test_legacy_source_keeps_existing_world_state_shape -q`

预期：失败，提示 `state_metrics` 或 `WorldState.metrics` 尚不存在。

- [ ] **步骤 3：写最小实现**

```python
class StateMetricDef(StrictModel):
    metric_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    initial_value: float = 0
    display_order: int = Field(ge=0)


class ProfileStateModifier(StrictModel):
    metric: str
    profile_key: str
    multiplier: float = 1
    offset: float = 0


class WorldState(DomainModel):
    cash_flow: float = 0
    customer_flow: float = 0
    competition_count: float = 0
    monthly_profit: float = 0
    payback_ratio: float = 0
    metrics: dict[str, float] = Field(default_factory=dict)
```

在 `make_initial_state` 中从 `source.state_metrics` 建立 `metrics`，只对数值型画像字段应用
`multiplier * value + offset`，并把 `budget` 对 `cash_flow` 的已有兼容逻辑保留。更新 reducer，
使动作效果能够更新声明的动态指标，同时拒绝未声明指标。提取 `read_world_metric(world_state, metric)`
供 reducer、结束判定和风险干预共享：先读旧五项字段，再读 `world_state.metrics`；未声明指标抛出
明确的场景配置错误。场景详情 presenter 返回 `state_metrics`，供前端决定展示哪些指标。

- [ ] **步骤 4：运行任务测试**

运行：`pytest tests/test_state_and_reducers.py tests/test_decision_source.py -q`

预期：通过，旧场景与新动态指标场景都能完成状态初始化和动作归约。

### 任务 2：冻结并传播画像快照

**文件：**

- 修改：`app/services/simulation_service.py`
- 修改：`app/engine/engine.py`
- 修改：`app/agents/inner_graph.py`
- 测试：`tests/test_profile_injection.py`
- 测试：`tests/test_user_participation.py`

**接口：**

- `SimulationState.user_profile` 是会话的不可变快照。
- `build_profile_summary(profile, decision_vars)` 的结果传给四个 Agent context。
- `SimulationService.restore_state(...)` 从 `simulation_sessions.user_profile` 恢复该快照。

- [ ] **步骤 1：写失败测试**

```python
def test_all_agent_contexts_receive_the_same_frozen_profile_summary():
    state = make_initial_state(
        source, variables, user_profile={"weekly_hours": 20, "assets": 500000},
    )
    summary = build_profile_summary(state.user_profile, state.decision_vars)
    contexts = engine.coordinator.observe(state, user_profile_summary=summary)

    assert {ctx.user_profile_summary for ctx in contexts.values()} == {summary}


def test_restored_session_uses_frozen_profile_after_profile_changes(client):
    session_id = _start_session_with_profile(client, {"weekly_hours": 20})
    _change_current_profile(client, {"weekly_hours": 60})
    detail = client.get(f"/api/sessions/{session_id}").json()
    assert detail["user_profile"]["weekly_hours"] == 20
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`pytest tests/test_profile_injection.py tests/test_user_participation.py -q`

预期：至少一个测试失败，说明 Agent 仅个人角色收到画像或会话详情未返回冻结快照。

- [ ] **步骤 3：写最小实现**

```python
def observe(self, state: SimulationState, *, user_profile_summary: str = "", ...):
    return {
        agent_id: AgentContext(
            ...,
            user_profile_summary=user_profile_summary,
        )
        for agent_id in self.agents
    }
```

保证创建会话时写入 `user_profile`，恢复会话时只读该列；会话详情响应增加只读的
`user_profile` 快照字段。不要在 `resume` 路径重新调用 `resolve_user_profile`。

- [ ] **步骤 4：运行任务测试**

运行：`pytest tests/test_profile_injection.py tests/test_user_participation.py -q`

预期：通过，四个角色和恢复推演都使用相同的冻结画像。

### 任务 3：建立明确的暂停原因和 API 契约

**文件：**

- 修改：`app/engine/models.py`
- 修改：`app/schemas/api.py`
- 修改：`app/schemas/events.py`
- 修改：`app/services/simulation_service.py`
- 修改：`app/api/simulation.py`
- 测试：`tests/test_resume_input_intent.py`
- 测试：新建 `tests/test_pause_protocol.py`

**接口：**

- `PauseReason = Literal["year_decision_required", "decision_preview_required", "intervention_required", "horizon_review"]`。
- `SimulationState.pause_reason: PauseReason | None`。
- `SimulationResponse.pause_reason` 与 `SimulationPausedPayload.pause_reason`。
- `POST /api/simulations/{session_id}/resume` 根据 `pause_reason` 验证输入，而不根据 `phase == "paused"` 猜测。

- [ ] **步骤 1：写失败测试**

```python
def test_year_pause_exposes_a_year_decision_reason(client):
    response = _start_and_pause(client, scenario_id="job_hunting")
    assert response["phase"] == "paused"
    assert response["pause_reason"] == "year_decision_required"


def test_intervention_pause_rejects_annual_decision_without_mutating_state(client):
    session_id = _start_at_intervention(client)
    before = _state(client, session_id)
    response = client.post(
        f"/api/simulations/{session_id}/resume", json={"choice": "增加学习投入"},
    )
    after = _state(client, session_id)
    assert response.status_code == 200
    assert response.json()["pause_reason"] == "intervention_required"
    assert after["world_state"] == before["world_state"]
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`pytest tests/test_pause_protocol.py tests/test_resume_input_intent.py -q`

预期：失败，响应中尚无 `pause_reason`，或风险干预被当作普通决策处理。

- [ ] **步骤 3：写最小实现**

```python
class SimulationState(DomainModel):
    ...
    phase: Phase = "input"
    pause_reason: PauseReason | None = None


def _to_response(state: SimulationState, **kwargs: object) -> SimulationResponse:
    return SimulationResponse(..., pause_reason=state.pause_reason, **kwargs)
```

设置原因的唯一位置：年度暂停设为 `year_decision_required`，待选择预览设为
`decision_preview_required`，LangGraph 风险 interrupt 设为 `intervention_required`，年限检查
设为 `horizon_review`。状态恢复、会话详情和 SSE 暂停事件均序列化该字段。

- [ ] **步骤 4：运行任务测试**

运行：`pytest tests/test_pause_protocol.py tests/test_resume_input_intent.py tests/test_horizon_review.py tests/test_interventions.py -q`

预期：通过，四种暂停都具有稳定、互斥的输入语义。

### 任务 4：把用户决策移到第 1 年之前并统一恢复顺序

**文件：**

- 修改：`app/engine/engine.py`
- 修改：`app/services/simulation_service.py`
- 修改：`app/api/stream.py`
- 测试：新建 `tests/test_yearly_decision_protocol.py`
- 测试：修改 `tests/test_graph_and_engine.py`

**接口：**

- 新会话顺序：`simulation.started(initial_analysis)` -> `simulation.paused(year_decision_required, year=0)`。
- 年度恢复顺序：用户决策 -> `year.started(year=n)` -> 四 Agent / Judge -> `year.completed(year=n)` -> 下一次暂停。
- `resume_events` 使用用户原始决策作为 `latest_decision`，不把它降级为固定 `steady` 策略。

- [ ] **步骤 1：写失败测试**

```python
def test_first_year_is_not_settled_before_user_decision(engine):
    events = list(engine.iter_events(variables))

    assert [event.event_type.value for event in events] == [
        "simulation.started", "simulation.paused",
    ]
    assert events[-1].payload.year == 0
    assert events[-1].state_snapshot.pause_reason == "year_decision_required"


def test_resume_decision_is_seen_by_all_agents_before_year_one_settlement(engine, db):
    state = _paused_initial_state(engine, db)
    events = list(engine.resume_events(state.session_id, state, "压缩固定成本，保留核心渠道", db=db))

    assert events[0].event_type.value == "year.started"
    assert events[0].payload.year == 1
    assert _latest_actions(events)[2].reason
    assert _latest_timeline(events).year == 1
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`pytest tests/test_yearly_decision_protocol.py tests/test_graph_and_engine.py -q`

预期：失败，现有 `iter_events` 会直接发出并结算 `year.started(year=1)`。

- [ ] **步骤 3：写最小实现**

```python
def _pause_for_year_decision(self, state: SimulationState) -> SimulationState:
    return state.model_copy(update={
        "phase": "paused",
        "pause_reason": "year_decision_required",
        "pending_intervention": None,
    })
```

在 `iter_events` 发出初步分析后持久化并返回年度决策暂停，不进入年度循环。
在 `resume_events` 中，仅当 `pause_reason == "year_decision_required"` 才进入一个年度循环；将
`choice` 写入 `state.user_message`，并将其传给全部 Agent context。每次年度结算后再次调用
`_pause_for_year_decision`，除非出现风险干预、达到年限或结束条件。
移除以 `PAUSE_EACH_YEAR` 作为产品行为开关的分支，统一流程始终在年度结算后暂停；该环境变量
不再决定用户是否有年度决策权。

- [ ] **步骤 4：运行任务测试**

运行：`pytest tests/test_yearly_decision_protocol.py tests/test_graph_and_engine.py tests/test_horizon_review.py -q`

预期：通过，全部场景在用户首个年度决策前都不发生年份推进。

### 任务 5：第一期前端协议接入

**文件：**

- 修改：`frontend/src/api/types.ts`
- 修改：`frontend/src/stores/simulation.ts`
- 修改：`frontend/src/views/SimView.vue`
- 修改：`frontend/src/components/sim/WorldStatePanel.vue`
- 修改：`frontend/src/stores/scenarios.ts`
- 测试：新建 `frontend/src/stores/simulation.spec.ts`（使用项目现有前端测试框架；若未配置，则在本任务中只运行 `npm run build`）

**接口：**

- `SimulationResponse.pause_reason?: PauseReason | null`。
- Pinia store 保存 `pauseReason`，SSE 和 HTTP 恢复响应均更新它。
- `SimView` 只在 `pauseReason === "year_decision_required"` 时显示自由决策输入；其他原因显示对应选项。
- `WorldStatePanel` 接受可选 `metricDefinitions`，优先按声明顺序渲染 `state.metrics`，没有声明时渲染兼容指标。
- `ScenarioDetail.state_metrics` 与后端场景详情响应同名，作为面板的唯一展示定义来源。

- [ ] **步骤 1：写失败测试或类型断言**

```ts
it('stores the explicit yearly decision pause reason', () => {
  const sim = useSimulationStore()
  sim.applyResponse({ ...pausedResponse, pause_reason: 'year_decision_required' })
  expect(sim.pauseReason).toBe('year_decision_required')
})
```

- [ ] **步骤 2：运行测试或构建并确认失败**

运行：`npm run build`

预期：在新增类型断言后，因 `pauseReason` 尚未定义而失败。

- [ ] **步骤 3：写最小实现**

```ts
export type PauseReason =
  | 'year_decision_required'
  | 'decision_preview_required'
  | 'intervention_required'
  | 'horizon_review'

const pauseReason = ref<PauseReason | null>(null)
```

在 `handleEvent` 和 `applyResponse` 写入该值；把模板中 `sim.phase === 'paused'` 的泛化分支替换为
按 `pauseReason` 的互斥分支。年度输入仍可输入自由文本，但风险干预和预览必须使用按钮选项。

- [ ] **步骤 4：运行任务验证**

运行：`npm run build`

预期：构建通过，类型覆盖所有新增后端字段。

## 第二期：灵活决策、动态建议与可见博弈

### 任务 6：用结构化意图替代关键词拒绝

**文件：**

- 修改：`app/services/input_intent.py`
- 修改：`app/engine/decision_preview.py`
- 修改：`app/api/simulation.py`
- 测试：`tests/test_input_intent.py`
- 测试：`tests/test_decision_preview_api.py`

**接口：**

- `DecisionIntent(kind, normalized_goal, matched_decision_id, confidence, explanation)`。
- 未能安全映射的 `year_decision_required` 输入返回 `pending_decision_preview` 或 `input_kind="clarify"`，不返回 422。
- 风险、预览、年限状态不调用年度自由意图映射。

- [ ] **步骤 1：写失败测试**

```python
def test_novel_annual_decision_returns_preview_instead_of_rejection(client):
    session_id = _start_at_year_decision(client, "general_startup")
    response = client.post(
        f"/api/simulations/{session_id}/resume",
        json={"choice": "把晚间服务改成预约制，并把营销预算转给老客复购"},
    )

    assert response.status_code == 200
    assert response.json()["pause_reason"] == "decision_preview_required"
    assert response.json()["pending_decision_preview"] is not None
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`pytest tests/test_input_intent.py tests/test_decision_preview_api.py -q`

预期：失败，当前实现把输入视为固定动作或返回笼统错误。

- [ ] **步骤 3：写最小实现**

```python
class DecisionIntent(BaseModel):
    kind: Literal["mapped", "preview", "clarify"]
    normalized_goal: str
    matched_decision_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    explanation: str
```

优先以已声明 catalogue 关键词和动作描述映射；无高置信映射时调用
`build_decision_previews` 生成三种可审计分支。分支只引用 `DecisionSource.action_effects` 中已声明
的动作；没有安全候选时保持原状态并返回针对性追问。

- [ ] **步骤 4：运行任务测试**

运行：`pytest tests/test_input_intent.py tests/test_decision_preview_api.py tests/test_resume_input_intent.py -q`

预期：通过，自由表达被理解、预览或追问，不会误推进状态。

### 任务 7：丰富四 Agent 输出和博弈记录

**文件：**

- 修改：`app/agents/contracts.py`
- 修改：`app/agents/llm_agent.py`
- 修改：`app/agents/inner_graph.py`
- 修改：`app/schemas/domain_models.py`
- 测试：`tests/test_agents.py`
- 测试：`tests/test_graph_and_engine.py`

**接口：**

- `AgentAction` 新增 `alternatives: list[str]`、`objection: str | None`、`stop_condition: str | None`，均有兼容默认值。
- `DebateRecord` 包含所有参与者的原始立场和裁决后的协调建议。
- Judge 仅在冲突阈值达到时触发一次修订，最多使用 `settings.max_judge_revisions`。
- 面向用户的内容固定为短字段：判断、依据、备选方案、风险或止损条件；禁止只输出长段提示词式文字。

- [ ] **步骤 1：写失败测试**

```python
def test_agent_action_contains_contextual_alternative_and_stop_condition():
    action = coordinator.propose(state, user_message="先压缩投入，验证需求")[0]
    assert action.alternatives
    assert action.stop_condition


def test_material_conflict_is_visible_in_debate_participants(engine):
    timeline = _run_conflicted_year(engine)
    assert timeline.debate is not None
    assert {p.agent_id for p in timeline.debate.participants} == {
        "market", "environment", "personal", "risk",
    }
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`pytest tests/test_agents.py tests/test_graph_and_engine.py -q`

预期：失败，动作缺少备选方案或止损条件。

- [ ] **步骤 3：写最小实现**

```python
class AgentAction(DomainModel):
    ...
    alternatives: list[str] = Field(default_factory=list)
    objection: str | None = None
    stop_condition: str | None = None
```

更新 LLM 的结构化输出 schema 和 Stub 的场景化 fallback；`build_debate` 从四个动作的
`position`、`reason` 与 `objection` 生成参与者记录，且在无实质分歧时返回 `None`。

- [ ] **步骤 4：运行任务测试**

运行：`pytest tests/test_agents.py tests/test_graph_and_engine.py -q`

预期：通过，四方观点、备选方案和止损条件可用且不改变规则结算。

### 任务 8：展示动态指标、方案预览和博弈建议

**文件：**

- 修改：`frontend/src/api/types.ts`
- 修改：`frontend/src/components/sim/WorldStatePanel.vue`
- 修改：`frontend/src/components/sim/DebatePanel.vue`
- 修改：`frontend/src/views/SimView.vue`
- 验证：`frontend` 构建与本地浏览器手动流程

**接口：**

- 世界状态面板按 `state_metrics` 显示场景相关标签、单位、当前值与状态变化。
- Agent 卡片显示“建议、依据、备选、止损条件”；博弈面板显示四方立场和裁决。
- 未映射决策预览显示系统理解、三种方案、风险等级和最坏损失，用户确认后才调用恢复接口。

- [ ] **步骤 1：写组件行为测试或准备最小夹具**

```ts
const state = { ...legacyWorldState, metrics: { execution_capacity: 60 } }
const definitions = [{ metric_id: 'execution_capacity', label: '执行能力', unit: '分', display_order: 1 }]
// 断言面板显示“执行能力”和“60 分”，而不显示不适用的固定指标。
```

- [ ] **步骤 2：运行构建并确认新增字段尚未被消费**

运行：`npm run build`

预期：当前构建可以通过，但动态指标和博弈扩展不会被展示；以组件测试失败作为行为门槛。

- [ ] **步骤 3：写最小实现**

```vue
<MetricRow
  v-for="metric in visibleMetrics"
  :key="metric.id"
  :label="metric.label"
  :value="metric.value"
  :unit="metric.unit"
/>
```

计算 `visibleMetrics`：有场景声明时只读声明指标；无声明时使用旧五项兼容列表。决策预览和
博弈组件只读取后端已确认结构化字段，不在前端推断动作效果。

- [ ] **步骤 4：运行任务验证**

运行：`npm run build`

预期：通过。使用 `npm run dev` 手动检查创业、求职、投资三个场景的首年决策、预览、干预和动态状态面板。

### 任务 9：跨场景端到端回归

**文件：**

- 新建：`tests/test_all_scene_yearly_protocol.py`
- 修改：`tests/test_scene_routing.py`（仅在路由真实行为需要修正时）

**接口：**

- 对所有 `scenarios/*.json`：创建会话后先得到 `year_decision_required`；提交决策后只推进一年；
  每次暂停的 `pause_reason` 与持久化状态一致。

- [ ] **步骤 1：写失败测试**

```python
@pytest.mark.parametrize("scenario_id", _all_scenario_ids())
def test_every_scene_uses_the_same_initial_and_yearly_protocol(client, scenario_id):
    session = _start_stream_session(client, scenario_id)
    initial = _session_state(client, session.id)
    assert initial["current_year"] == 0
    assert initial["pause_reason"] == "year_decision_required"

    resumed = client.post(
        f"/api/simulations/{session.id}/resume", json={"choice": "先小范围验证，再根据结果调整投入"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["year"] == 1
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`$env:LLM_USE_STUB='1'; $env:RAG_ENABLED='0'; $env:MCP_ENABLED='0'; $env:DATABASE_URL='sqlite://'; $env:CHECKPOINTER_URL='memory'; pytest tests/test_all_scene_yearly_protocol.py -q`

预期：在第一期完成前失败，原因是部分场景会直接推进第 1 年或暂停语义不一致。

- [ ] **步骤 3：只修复测试暴露的协议偏差**

按失败场景补齐决定变量夹具或兼容映射；不得为通过测试而在测试中绕过真实 API。

- [ ] **步骤 4：运行完整验证**

运行：`$env:LLM_USE_STUB='1'; $env:RAG_ENABLED='0'; $env:MCP_ENABLED='0'; $env:DATABASE_URL='sqlite://'; $env:CHECKPOINTER_URL='memory'; pytest -q`

预期：所有新增协议测试通过；若保留已有且无关的场景路由断言失败，单独记录其原因，不掩盖它。
