# MVP-0 缺口补齐执行计划（subagent-driven-development）

> 背景：codex 已完成 MVP-0 后端主体（26 测试全绿），但有两个缺口：
> - **缺口①**：`app/db/` 未建，推演状态只活内存，不落库（PRD 7.3 已设计 9 张表，缺落地）
> - **缺口②**：两层编排用普通 Python 类，未用 LangGraph 的 `StateGraph` + `interrupt()`（AGENTS.md 红线）
>
> 策略：subagent 驱动，模块 A 做完即审查，再派模块 B。TDD 先行，不擅自 commit。

## 模块 A：数据库落库（缺口①）—— 先做，做完审查
- **A1** `pyproject.toml` 加 `sqlalchemy>=2.0`（开发期 `create_all`，alembic 暂不加）；venv 安装
- **A2** `app/db/models.py`：SQLAlchemy 2.0 `Base` 子类，9 张表严格对齐 PRD 7.3.1 DDL
  - `users`（MVP-0 简化内部标识，不接鉴权）
  - `scenarios / assets / kb_chunks / simulation_sessions / simulation_messages / simulation_events / user_profiles / agent_memories`
  - 开发期 SQLite：JSON 用 `JSON` 类型；`embedding` 用 JSON 占位（不引 pgvector）；uuid 用 `Uuid` 类型或 `String(36)`+`default=str(uuid4)`；时间戳 `DateTime(timezone=True)`
- **A3** `app/db/session.py`：`engine`(sqlite:///./yanjie_dev.db) + `SessionLocal` + `init_db()`(`create_all`) + `get_db` 依赖
- **A4** `tests/test_db_models.py`（TDD 先写）：`create_all` 建出 9 表（inspector 校验表名）+ 每表 insert→select→update→delete round-trip
- **A5**（加分）`app/engine/engine.py` 增加持久化：推演结束写 `simulation_sessions`（world_state/timeline/result/score…），保持 `iter_events/aiter_events/run` 公共行为不变，避免循环导入
- **验收**：`pytest tests/test_db_models.py` 全绿；全量 `pytest` 仍 26+ 绿；9 表齐全；无 pgvector 依赖；无循环导入

## 模块 B：LangGraph 框架对齐（缺口②）—— A 审查通过后做
- **B1** `app/engine/graph.py` → 外层 `StateGraph`：timeline 状态推进节点 + `check_ending`；关键节点干预用 LangGraph `interrupt()`
- **B2** `app/agents/inner_graph.py` → 内层 `StateGraph`：4 Agent + Judge 调度（保留 stub 解耦，MVP-0 不接真 LLM）
- **B3** 保持 `SimulationEngine.iter_events` / SSE 端点公共契约与输出不变（26 测试必须仍过）
- **B4** `tests/` 验证两层 graph 行为与重构前一致（序列/终态/干预点不变）
- **验收**：全量 `pytest` 绿；LangGraph `StateGraph`+`interrupt()` 已用；行为零回归

## 红线（全程）
- TDD 先行（红→绿→重构）
- 不擅自 commit/push
- 异常统一兜底，不暴露堆栈
- 决策源驱动、LLM 只做生成层；`nodes.py` 纯函数
- 测试用 `C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe -m pytest`
