# Code Review — 模块 B：LangGraph 框架对齐（缺口②）

**审查人**：主线 agent（内联实现 + trust-but-verify）
**验证手段**：亲自跑 `pytest tests/ -v` → **41 passed, exit 0**（含 4 条新增结构测试）

## Spec Compliance（AGENTS.md 红线逐条核对）

| 红线 | 落地 | 证据 |
|---|---|---|
| 两层 LangGraph StateGraph | ✅ | 外层 `graph.py` 4 节点 prepare→apply_actions→check_ending→append_year；内层 `inner_graph.py` 4 节点 observe→propose→validate→emit |
| 关键节点干预用 interrupt() | ✅ | `intervention_graph.py` import `from langgraph.types import interrupt`，`_check_and_apply` 节点在 pending 且 choice=None 时调 `interrupt()` |
| nodes.py 保持纯函数 | ✅ | graph.py 节点直接委托 `prepare_state`/`apply_supplied_actions`/`check_ending`/`append_year`，零 LLM 调用 |
| LLM/Agent 交互放 agents/ | ✅ | `AgentCoordinator.propose()` 走 `self._graph.invoke()`，4 Agent stub 在 `app/agents/` |
| 评分/风险/结局放 engine/scoring.py | ✅ | 未改动，`_finalize()` 仍调 `compute_score`/`extract_risks`/`build_action_plan` |
| TypedDict 状态容器 | ✅ | `OuterState`/`InnerState`/`InterventionState` 均为 `TypedDict` 子类 |
| 公共契约零回归 | ✅ | `iter_events`/`run`/`persist`/`aiter_events` 签名不变，41 测试全绿 |

## Code Quality

- ✅ 三个 StateGraph 编译产物均为 LangGraph Runnable（`invoke` + `get_graph` 可用）
- ✅ `AgentCoordinator.__init__` 持有 `self._graph`，`propose()` 改走图编排，行为等价
- ✅ engine.py 显式检测 `__interrupt__` 返回值（LangGraph 0.6.x 同步 invoke 不抛异常，返回带 `__interrupt__` 键的 dict）
- ✅ 结构测试 `test_langgraph_structure.py` 断言：编译图类型、节点名集合、源码含 `StateGraph`/`interrupt` import
- ✅ DBG 插桩已全部撤除

## 修复的关键 Bug

**根因**：干预检查块在 `iter_events` 的 for 循环**外部**（缩进层级错误），而循环内 `state.phase == "completed"` 时 `return` 直接退出生成器，永远到不了循环外的干预检查。

**症状**：`test_interventions.py` 两个测试 FAIL；DBG 输出为空（干预图节点从未执行）。

**修复**：将干预检查移入 for 循环内部，位于 `graph.invoke()` 之后、completion 检查之前。每年处理完毕后立即检查待决干预——有 pending 且无 choice 则暂停；有 choice 则 apply 后继续。

## 问题清单

| 级别 | 位置 | 说明 | 处置 |
|---|---|---|---|
| Minor | `engine.py` L159-163 | `iv.get("__interrupt__")` 直接访问 LangGraph 内部返回结构，非公开 API | MVP-0 可接受；LangGraph 升级时需适配 |
| Minor | `intervention_graph.py` L58 | apply 后 `new_state.phase = "simulating"` 硬编码重置 | 当前正确（干预后继续推演）；若未来干预可导致提前结束需调整 |

## 结论

**Critical / Major：无。** 两项 Minor 均为 MVP-0 合理实现，不阻塞。
模块 B 通过。缺口①（数据库）+ 缺口②（LangGraph）均已补齐，41 测试零回归。
