# 场景库展示修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让场景库完整展示本地的十个场景，并确保可见字段和 Agent 名称均为中文。

**Architecture:** 本地 `scenarios/*.json` 是 MVP 场景列表唯一来源。新增展示转换模块，为详情接口添加中文字段标签和固定的四个中文 Agent 名称，保留原始字段名供前端提交和推演引擎使用。前端仅展示这些中文名称；对比页面路由与接口保留，但从主导航移除。

**Tech Stack:** FastAPI、Pydantic、pytest、Vue 3、TypeScript、Vite。

## Global Constraints

- 场景 JSON 决定推演事实与校验规则，展示层不得修改其原始字段名。
- 所有新增行为先由失败测试覆盖。
- 不初始化 Git、不提交或推送。

### Task 1: 固定场景列表来源

**Files:**
- Modify: `tests/test_api.py`
- Modify: `app/services/scenario_service.py`

- [ ] 写一个 API 测试，断言 `/api/scenarios` 返回十个本地场景 ID，即使数据库仅保存奶茶场景也不丢失其他场景。
- [ ] 运行该测试，确认现有 DB 优先逻辑导致失败。
- [ ] 改为始终枚举 `ScenarioLoader.list_all()`，保留读取异常的跳过日志。
- [ ] 重新运行测试，确认通过。

### Task 2: 提供统一的中文展示字段

**Files:**
- Create: `app/services/scenario_presenter.py`
- Modify: `app/api/scenarios.py`
- Modify: `tests/test_api.py`

- [ ] 写一个详情接口测试，断言决策变量包含中文 `label`，四位 Agent 返回固定中文名称。
- [ ] 运行该测试，确认当前接口没有 `label` 而失败。
- [ ] 增加集中字段映射和 Agent 映射，详情接口序列化时添加展示名。
- [ ] 重新运行测试，确认通过。

### Task 3: 前端消费展示名并收起对比入口

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/utils/decision-vars.ts`
- Modify: `frontend/src/views/LibraryView.vue`
- Modify: `frontend/src/components/layout/NavBar.vue`

- [ ] 将详情类型定义为带 `label` 的决策变量及具名 Agent。
- [ ] 表单工具直接读取接口的 `label`，删除重复的字段翻译表。
- [ ] 场景详情不再可见 `scenario_id`，只显示中文字段标签和中文 Agent 名称。
- [ ] 从主导航移除“对比”，保留路由和后端接口。

### Task 4: 回归验证

- [ ] 运行 `python -m pytest -q`。
- [ ] 在 `frontend` 下运行 `npm.cmd run build`。
- [ ] 检查场景库接口返回十个场景、场景详情不泄漏英文展示名称。
