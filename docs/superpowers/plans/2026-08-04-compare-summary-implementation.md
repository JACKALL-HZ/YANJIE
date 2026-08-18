# A/B 对比摘要 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 A/B 推演结果转换为可直接阅读的中文推荐、指标差异与风险摘要。

**Architecture:** `app/engine/compare.py` 保持纯函数并在现有数值比较结果上增加结构化摘要；`CompareResponse` 暴露该摘要；`CompareView.vue` 按摘要渲染固定中文区域。推演引擎、数据库和 LLM 均不改动。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、pytest、Vue 3、TypeScript、ECharts。

## Global Constraints

- 对比结果不写入历史会话。
- 显示文案必须中文，不展示原始指标键、动作 ID、结果枚举或 JSON。
- 比较结论必须确定性可复现。
- 先写失败测试，再写最小实现；不创建 Git 提交。

---

### Task 1: 对比摘要纯函数与接口契约

**Files:**
- Modify: `app/engine/compare.py`, `app/schemas/api.py`
- Test: `tests/test_scoring_and_compare.py`

**Interfaces:**
- `compare_states(...)` 在既有数值维度外返回 `summary`。
- `summary` 包含 `recommendation`、`metrics` 与 `risks`，所有用户展示字段均为中文。

- [ ] **Step 1: 写失败测试**

```python
def test_compare_summary_uses_chinese_metrics_and_recommends_better_plan():
    result = compare_states(
        {"cash_flow": 100000, "customer_flow": 180, "competition_count": 30,
         "monthly_profit": 30000, "payback_ratio": 0.8},
        "steady",
        {"cash_flow": 50000, "customer_flow": 100, "competition_count": 55,
         "monthly_profit": 10000, "payback_ratio": 0.3},
        "timeout",
        score_a=80,
        score_b=55,
    )
    assert result["summary"]["recommendation"]["winner"] == "A"
    assert result["summary"]["metrics"][0]["label"] == "现金储备"
    assert "cash_flow" not in str(result["summary"])
```

- [ ] **Step 2: 验证测试失败**

Run: `python -m pytest tests/test_scoring_and_compare.py -v`

Expected: 因 `score_a` 参数和 `summary` 尚不存在而失败。

- [ ] **Step 3: 实现最小中文摘要**

```python
def compare_states(..., score_a: float | None = None, score_b: float | None = None) -> dict[str, Any]:
    return {
        ...,
        "summary": build_compare_summary(state_a, state_b, score_a, score_b),
    }
```

固定映射五项世界指标；根据评分和指标生成推荐与风险提示。更新 `CompareResponse.comparison` 类型，允许摘要对象。

- [ ] **Step 4: 验证聚焦测试**

Run: `python -m pytest tests/test_scoring_and_compare.py tests/test_api.py -v`

Expected: PASS。

### Task 2: 中文对比页渲染

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/views/CompareView.vue`
- Test: frontend build

**Interfaces:**
- `CompareResponse.comparison.summary` 的 TypeScript 类型与后端返回一致。
- 页面使用 `summary.recommendation`、`summary.metrics` 和 `summary.risks`。

- [ ] **Step 1: 添加前端摘要类型**

```ts
export interface CompareSummary {
  recommendation: { winner: 'A' | 'B' | 'tie'; title: string; reason: string }
  metrics: Array<{ label: string; a: string; b: string; delta: string; better: 'A' | 'B' | 'tie' }>
  risks: Array<{ plan: 'A' | 'B'; level: string; message: string }>
}
```

- [ ] **Step 2: 渲染推荐、固定指标表与双方风险**

移除 `comparisonEntries` 和基于键名的 `JSON.stringify` 渲染。评分维度、趋势图例和单位均使用中文。

- [ ] **Step 3: 构建前端**

Run: `npm.cmd run build`

Expected: TypeScript 检查和 Vite 构建均通过。

### Task 3: 模块审查与交接

**Files:**
- Modify: `docs/开发交接清单.md`
- Test: 全量后端测试、前端构建

- [ ] **Step 1: 验证不持久化约束**

确认 `/compare` 不传入数据库会话给 `SimulationService.compare`，且没有对 `SimulationRepo` 的写入。

- [ ] **Step 2: 运行完整回归**

Run: `python -m pytest -q` and `npm.cmd run build`

Expected: 全部通过。

- [ ] **Step 3: 更新交接清单**

记录摘要接口的字段、确定性推荐规则和“对比不持久化”的边界。
