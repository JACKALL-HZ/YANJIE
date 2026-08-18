# Simulation Context Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 切换推演场景时不复用旧场景上下文，主页对话能够正确启动对应场景，并用测试确认不同用户和游客会话互不可见。

**Architecture:** 保留 `KeepAlive` 以保持同一场景的输入体验，但让 `SimView` 监听路由场景变化；场景变化时清理本地上下文、Pinia 推演状态和场景详情，再以新场景默认参数初始化。主页对话继续通过 `BreakdownView` 的结构化拆解进入 `SimView`，并补充入口测试；后端继续使用现有 `user_id`/`owner_key` 归属校验，新增跨身份 API 集成测试。

**Tech Stack:** Vue 3 + TypeScript + Pinia + Vue Router；FastAPI + pytest + SQLite 测试数据库。

## Global Constraints

- 坚持“决策源驱动、LLM 只做生成层”。
- 所有核心请求和响应使用现有 TypeScript/Pydantic 类型，不新增散乱状态字段。
- 不把不同场景的字段带入新场景；不存在场景时不能默认回退到奶茶场景。
- 登录用户按 `user_id` 隔离，游客按 `X-Yanjie-Guest-Id` 隔离；RAG 公共知识不做用户隔离。
- 不提交 Git；每个模块完成后运行对应测试和构建。

---

### Task 1: 场景切换时重置推演工作台

**Files:**
- Modify: `frontend/src/views/SimView.vue`
- Modify: `frontend/src/stores/simulation.ts`
- Test: `frontend/src/views/SimView.spec.ts` or existing frontend test location if configured

**Interfaces:**
- `SimView` consumes `route.params.scenarioId` and `useSimulationStore()`.
- `useSimulationStore.reset()` remains the public reset operation and must clear the active session state.

- [ ] **Step 1: Write the failing test**

  Add a component-level regression test that mounts `SimView`, navigates from `/sim/career_advance` to `/sim/grad_exam`, and asserts the new route uses `grad_exam` rather than the original scenario and that the previous simulation store data is reset.

- [ ] **Step 2: Run the focused frontend test**

  Run `npm.cmd run test -- --run frontend/src/views/SimView.spec.ts` from `E:/衍界 YANJIE/frontend`.
  Expected result: FAIL because `scenarioId` is initialized only once and the cached component does not react to route changes.

- [ ] **Step 3: Implement the minimal route-aware reset**

  In `SimView.vue`, watch `route.params.scenarioId`; when the new non-empty ID differs from the current ID, stop/reset the simulation store, clear `extractedVars`, `cachedVars`, `chatMessages`, `msgSeq`, `showCharts`, and reload the matching scenario detail. Keep the existing state when the route points to the same scenario.

  In `simulation.ts`, make `reset()` abort an active stream and clear every session-bound field already exposed by the store, including `scenarioId`, so the old session cannot be rendered while the new detail is loading.

- [ ] **Step 4: Run the focused frontend test**

  Run `npm.cmd run test -- --run frontend/src/views/SimView.spec.ts` and expect PASS.

- [ ] **Step 5: Run the frontend build**

  Run `npm.cmd run build` from `E:/衍界 YANJIE/frontend` and expect exit code 0.

### Task 2: 主页对话入口回归

**Files:**
- Inspect/modify: `frontend/src/views/BreakdownView.vue`
- Inspect/modify: `frontend/src/components/chat/OnboardingChat.vue`
- Test: `frontend/src/views/BreakdownView.spec.ts` or existing frontend test location if configured

**Interfaces:**
- `BreakdownView` calls `POST /api/assistant/breakdown` and routes to `sim` with the returned `scenario_id` and extracted variables.
- `OnboardingChat` accepts an optional locked scenario and emits the selected scenario plus history to `SimView`.

- [ ] **Step 1: Write the failing test**

  Add a regression test for a homepage query such as `“我要考研，北京大学，准备八个月”`; mock the breakdown response with `scenario_id: "grad_exam"`, then assert navigation contains `scenarioId=grad_exam` and does not retain a previous scenario query.

- [ ] **Step 2: Run the focused frontend test**

  Run `npm.cmd run test -- --run frontend/src/views/BreakdownView.spec.ts` from `E:/衍界 YANJIE/frontend`.
  Expected result: the test exposes any mismatch between the breakdown response, route params, and query variables.

- [ ] **Step 3: Implement only the broken handoff**

  Ensure the route handoff uses the returned `scenario_id`, encodes only fields defined by that scenario, and clears stale scenario query values before navigation. Do not use a hard-coded startup scenario or generic business fields for a non-startup scene.

- [ ] **Step 4: Run the focused test and build**

  Run the focused test and then `npm.cmd run build`; both must pass.

### Task 3: 双身份会话隔离回归测试

**Files:**
- Create: `tests/test_session_isolation.py`
- Inspect/modify: `app/api/dependencies.py` only if a test finds an actual ownership defect
- Inspect/modify: `app/api/sessions.py` only if list filtering is inconsistent with detail filtering

**Interfaces:**
- `POST /api/simulations` accepts `X-Yanjie-Guest-Id` for anonymous sessions and the existing test authentication override for logged-in users.
- `/api/sessions`, `/api/sessions/{id}`, `/api/sessions/{id}/report-detail`, `/api/simulations/{id}/resume`, and `/api/simulations/{id}/ask` must enforce the same owner.

- [ ] **Step 1: Write the failing tests**

  Add tests that create sessions for two distinct guest headers and two distinct authenticated users, then assert the other identity receives `404` for detail/report/resume/ask and cannot see the session in `GET /api/sessions`.

- [ ] **Step 2: Run the isolation tests**

  Run `pytest -q tests/test_session_isolation.py` from `E:/衍界 YANJIE`.
  Expected result: PASS with the current ownership implementation; if any case fails, the failure identifies the exact endpoint that leaks or accepts another owner.

- [ ] **Step 3: Fix only a failing ownership path**

  Reuse `assert_session_owner` at every session-bound endpoint. Return the existing not-found response for foreign session IDs so the API does not disclose whether another user’s session exists.

- [ ] **Step 4: Run the full verification suite**

  Run `pytest -q` and `npm.cmd run build`. Both must exit successfully before declaring the fix complete.

---

## Self-review

- Scene switching, homepage handoff, and cross-user isolation each have a separate testable task.
- No task changes the shared RAG knowledge boundary; RAG remains public and scenario-routed.
- The plan does not assume a Git commit because the repository has no usable Git workflow.
