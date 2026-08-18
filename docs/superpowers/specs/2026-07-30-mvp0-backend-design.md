# 衍界 YanJie AI MVP-0 后端设计决策

> 日期：2026-07-30
> 状态：已确认，作为 `docs/superpowers/plans/2026-07-30-mvp0-backend.md` 的设计依据

## 目标

在本地无外部服务、无真实 LLM、无数据库的条件下，跑通一个可测试、可演示的后端闭环：

`决策变量 → 4 个 Agent 结构化行动 → 确定性状态推进 → 文本时间线 → 干预规则 → 结局/评分/风险/行动计划 → A/B 对比 → SSE 事件流`

MVP-0 的重点是验证决策源解耦和推演引擎边界，不提前验证生产基础设施。

## 明确不做

- 不接真实 LLM、真实 RAG、Chroma、MCP 或外部数据源。
- 不接 SQLAlchemy、SQLite 持久化、PostgreSQL、pgvector、Redis 或 Alembic。
- 不实现 LangGraph `interrupt()` 的跨请求断点续推。
- 不做真实 token 流；SSE 只流推演阶段事件。
- 不做账号、鉴权、用户画像长期记忆和生产部署。

这些能力保留清晰的接口边界，另开 MVP-1/MVP-2 计划实现。

## 核心决策

### 1. 决策源是唯一业务事实来源

`scenarios/*.json` 定义变量、Agent 能力、世界状态初值、行动效果、干预规则和结局条件。加载后必须通过 Pydantic 模型校验，禁止在节点里散落字符串阈值和隐式字段。

LLM 或 stub 只返回 `AgentAction`，不能直接修改 `WorldState`，也不能决定最终结局。

### 2. 状态推进采用“行动 → 效果 → 归并 → 判定”

每一年按以下顺序执行：

1. 外层图读取当前 `SimulationState`。
2. 内层 Agent 协调器为 4 个 Agent 生成结构化行动。
3. 纯函数根据决策源把行动解析为 `StateEffect`。
4. 纯函数归并效果，得到新的 `WorldState` 和 `EventRecord`。
5. 纯函数检查干预和结局。
6. 生成不可变的 `TimelineNode`，再进入下一年或结算。

这样可以单独替换 Agent、模型或提示词，而不会改变 AC7 的结局判定。

### 3. MVP-0 保留两层编排，但不伪装生产级 Agent

- 外层 LangGraph 负责年度循环、终止条件和阶段路由。
- 内层协调器保留 `observe → propose → validate → emit` 四步接口，四个 Agent 使用 stub 实现。
- 内层节点只负责产生/校验行动，不负责写世界状态。
- MVP-1 再把内层协调器替换为真实 LLM、多 Agent 工具调用和 Judge 自洽修复。

### 4. 干预先做确定性策略，不提前引入 `interrupt()`

MVP-0 支持两种可测试行为：

- 请求提供 `intervention_choices`，引擎在触发规则时应用指定选项；
- 没有选择时返回 `phase="paused"` 和 `pending_intervention`，不继续推进。

不在 MVP-0 实现跨请求 checkpoint、LangGraph `interrupt()`、恢复 token 或数据库存档。这样可以验证规则与效果，又不会把交互状态、持久化和并发问题提前混入核心引擎。

### 5. SSE 流的是领域事件，不是事后切片

引擎提供 `iter_events()`，每完成一个可提交步骤就产生一个 `SimulationEvent`。SSE 路由直接消费这个迭代器，事件顺序固定：

`simulation.started → year.completed × N → intervention.pending? → simulation.completed`

如果发生可处理错误，流发送一个 `simulation.failed` 事件并结束。MVP-0 不声称这是 LLM token 流。

### 6. API 使用 Pydantic 契约，不接受任意 dict

客户端不能通过请求体切换真实模型。stub 开关由配置和测试依赖注入控制；API 只接收场景、决策变量、用户画像和干预选项。

场景路径由配置的根目录解析并校验 `scenario_id`，禁止直接拼接用户输入形成任意文件路径。

### 7. MVP-0 的存储边界是内存

场景从 JSON 只读加载并缓存；模拟结果在请求生命周期内以内存对象存在。`SimulationRepository` 作为未来可注入协议保留，但不在本计划引入数据库模型。

## 关键接口

```python
class SimulationEngine:
    def run(
        self,
        decision_vars: DecisionVars,
        user_profile: UserProfile | None = None,
        intervention_choices: dict[int, str] | None = None,
    ) -> SimulationState:
        ...

    def iter_events(
        self,
        decision_vars: DecisionVars,
        user_profile: UserProfile | None = None,
        intervention_choices: dict[int, str] | None = None,
    ) -> Iterator[SimulationEvent]:
        ...
```

```python
class AgentProtocol(Protocol):
    agent_id: str

    def propose(self, context: AgentContext) -> AgentAction:
        ...
```

```python
def apply_actions(
    world_state: WorldState,
    actions: list[AgentAction],
    decision_source: DecisionSource,
) -> TransitionResult:
    ...

def judge_ending(
    world_state: WorldState,
    year: int,
    end_conditions: EndConditions,
) -> EndingResult:
    ...
```

## 验证标准

- stub 模式不需要任何 API key 或外部服务即可通过全量测试。
- 相同决策源和决策变量得到稳定的 stub 结果。
- 改变预算等变量能改变状态路径，低预算能触发 `bankrupt`。
- 同一组 `WorldState` 下替换 Agent 的 reason 或 action 文案不会改变结局判定。
- SSE 测试验证事件名、顺序、序号和终止事件，不依赖字符串碰巧包含 `"result"`。
- 非法场景、非法变量、重复干预和超出最大年份均有明确错误或终态。
