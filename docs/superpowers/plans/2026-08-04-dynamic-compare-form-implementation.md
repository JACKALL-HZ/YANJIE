# 场景驱动 A/B 对比表单 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于所选场景的变量定义动态渲染并提交 A/B 对比参数。

**Architecture:** 后端现有场景详情接口提供变量元数据。前端新增小型纯工具函数，将变量定义转换为默认表单值和提交值；`CompareView.vue` 负责加载详情、展示两套表单和状态切换。

**Tech Stack:** FastAPI、pytest、Vue 3、TypeScript、Vite。

## Global Constraints

- 前端不能复制或修改场景校验规则。
- 必填变量全部可见，非必填变量默认折叠。
- 只提交已填写的变量；对比结果不落库。
- 先写失败测试，再写最小实现；不创建 Git 提交。

---

### Task 1: 固定场景变量接口契约

**Files:**
- Modify: `tests/test_scenarios.py`
- Modify: `frontend/src/api/types.ts`

**Interfaces:**
- `ScenarioDetail.decision_vars` 是 `DecisionVarDefinition[]`，每项包含名称、类型、必填标记、默认值和数值范围。

- [ ] **Step 1: 写失败接口测试**

```python
def test_scenario_detail_returns_form_ready_decision_variables(client):
    response = client.get("/api/scenarios/grad_exam")
    fields = response.json()["decision_vars"]
    assert fields[0]["name"] == "target_school"
    assert fields[2]["value_type"] == "integer"
    assert fields[2]["minimum"] == 1
```

- [ ] **Step 2: 验证接口契约**

Run: `python -m pytest tests/test_scenarios.py -v`

Expected: PASS，确认无需为前端新增第二个元数据接口。

- [ ] **Step 3: 添加 TypeScript 元数据类型**

```ts
export interface DecisionVarDefinition {
  name: string
  value_type: 'integer' | 'number' | 'string'
  required: boolean
  default: string | number | null
  minimum?: number | null
  maximum?: number | null
}
```

将 `ScenarioDetail.decision_vars` 改为该数组类型。

### Task 2: 动态表单状态与提交

**Files:**
- Create: `frontend/src/utils/decision-vars.ts`
- Modify: `frontend/src/views/CompareView.vue`
- Test: `npm.cmd run build`

**Interfaces:**
- `createDecisionValues(definitions)` 仅返回有默认值的变量。
- `toDecisionPayload(definitions, values)` 去除空字符串、空值和无定义变量。

- [ ] **Step 1: 新增表单值工具函数**

```ts
export function createDecisionValues(definitions: DecisionVarDefinition[]): Record<string, string | number> {
  return Object.fromEntries(definitions.filter((item) => item.default !== null).map((item) => [item.name, item.default]))
}
```

- [ ] **Step 2: 使用场景详情驱动表单**

在场景选择变化时调用 `scenarios.fetchDetail(id)`，重置 A/B 表单；以 `required` 分组渲染字段，提交时调用 `toDecisionPayload`。

- [ ] **Step 3: 构建前端**

Run: `npm.cmd run build`

Expected: PASS。

### Task 3: 回归与交接

**Files:**
- Modify: `docs/开发交接清单.md`
- Test: full backend suite and frontend build

- [ ] **Step 1: 验证考研与奶茶场景请求**

通过 API 测试验证 `grad_exam` 与 `milktea_startup` 的变量定义；页面构建确保动态模板类型正确。

- [ ] **Step 2: 完整回归**

Run: `python -m pytest -q` and `npm.cmd run build`

Expected: PASS。

- [ ] **Step 3: 更新交接清单**

记录动态表单从场景详情读取变量，场景切换会重置表单的约定。
