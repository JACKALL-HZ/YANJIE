# Code Review — 模块 A：数据库落库（缺口①）

**审查人**：主线 agent（trust-but-verify，非盲信 subagent）
**验证手段**：亲自跑 `pytest E:/衍界 YANJIE -q` → **37 passed, exit 0**

## Spec Compliance
- ✅ 9 张表齐全（users/scenarios/assets/kb_chunks/simulation_sessions/simulation_messages/simulation_events/user_profiles/agent_memories）
- ✅ 字段严格对齐 PRD 7.3.1 DDL（逐列核对）
- ✅ JSON 列用 `sqlalchemy.JSON`；`kb_chunks.embedding` 以 JSON 占位，**无 pgvector 依赖**
- ✅ uuid 主键用 `String(36)`+`uuid4()`（避开 SQLite `Uuid(CHAR(32))` 截断 36 位 uuid）
- ✅ `app/db` 单向 import models，无循环导入

## Code Quality
- ✅ 类型标注（Mapped/mapped_column）、docstring、snake_case、4 空格
- ✅ `session.py` 提供 `init_db()`(create_all) + `get_db()` 依赖生成器，契约清晰
- ✅ TDD：`test_db_models.py` 先写 9 表 create_all + 每表 CRUD round-trip；`conftest.py` autouse `_clean_db` 按依赖逆序 wipe 隔离共享 dev DB
- ✅ `engine.persist()` 用 try/except 容错（落库失败不影响推演返回），符合"统一兜底"红线

## 问题清单
| 级别 | 位置 | 说明 | 处置 |
|---|---|---|---|
| Minor | `models.SimulationSession.scenario_id` | 类型 `String(255)` + `FK→scenarios.scenario_id`；PRD 7.3.1 为 `uuid NOT NULL REFERENCES scenarios(id)`。MVP-0 简化：决策源字符串主键更直接，persist 时 upsert scenarios 拿不到 uuid id 前用字符串更自然 | 不阻塞；生产迁移前改为 `FK→scenarios.id`(uuid) |
| Minor | `SimulationSession.scenario_id` nullable | PRD 为 NOT NULL；MVP-0 容错可接受 | 同上，生产前修正 |

## 结论
**Critical / Major：无。** Minor 两项均为 MVP-0 合理简化，不阻塞。
模块 A 通过，进入模块 B（LangGraph 框架对齐）。
