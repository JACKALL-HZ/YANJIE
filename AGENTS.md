# 仓库指南

## Agent 工作规则

收到任务后，先判断是否有匹配的 skill；哪怕只有很小可能，也要先检查再行动。涉及新功能、组件、行为修改或方案创造时，先做设计分析，再进入实现。实现功能或修复 bug 时遵循 TDD：先写能失败的测试，再写最小实现。声明完成前必须运行验证命令，并用实际结果支撑结论。

常用触发规则：

- 创造性工作或需求不清时，使用 `brainstorming`。
- 多步骤实现前，使用 `writing-plans`。
- 执行已有计划时，使用 `executing-plans` 或 `subagent-driven-development`。
- 修复 bug、测试失败或异常行为时，使用 `systematic-debugging`。
- 写功能或修 bug 前，使用 `test-driven-development`。
- 完成重要变更或合并前，使用 `requesting-code-review` 与 `verification-before-completion`。
- 收到 review 反馈后，使用 `receiving-code-review`。
- 需要隔离开发环境时，使用 `using-git-worktrees`。
- 需要并行处理 2 个以上相互独立任务时，使用 `dispatching-parallel-agents`。

仅在用户显式要求时使用中文专项 skill，例如 `chinese-code-review`、`chinese-commit-conventions`、`chinese-documentation`、`chinese-git-workflow`。如果当前环境未暴露某个 skill 或工具，说明限制后采用最接近的本地流程。

## 前后端技术栈与总体架构

本仓库服务于「衍界 YanJie AI」：一个 AI 决策推演工作台，当前阶段为 MVP-0（纯后端 + Mock LLM stub + 文本时间线）。根目录 Markdown 文件保存 PRD、实现计划、设计思路和面试说明；根目录 HTML 文件是 UI 原型。

PRD 明确的目标技术栈如下：

- 前端：Vue3 + TypeScript + Tailwind + Three.js，用于场景库、模拟主界面、A/B 对比、个人画像和分支时间线可视化。
- 后端：Python 3.12 + FastAPI + LangGraph + LangChain，负责 API、SSE 流式输出、两层状态机、多 Agent 编排和模型/工具调用。
- 数据层：开发期使用 SQLite（业务库）+ Chroma（向量库，本地文件）；生产期迁移 PostgreSQL + pgvector + Redis。
- RAG/Embedding：决策知识库通过 `VectorStore` 抽象层切换 Chroma/pgvector；embedding 固定 bge-m3，保证开发与生产向量空间一致。
- LLM：快模型优先 DeepSeek/本地小模型，慢模型使用 Claude/GPT 做关键节点质量保障，通过分层路由选择。
- 工具接入：Python MCP server 暴露市场、政策、竞品、人口等查询工具。
- 部署：开发期零部署、本地文件优先；生产期可用 Docker Compose 拉起 PostgreSQL/pgvector/Redis/后端服务，前端静态产物独立托管。

系统主链路：前端通过 HTTP/SSE 调 FastAPI；API 调 `SimulationEngine`；外层 LangGraph 推进时间线；内层 LangGraph 调度 4 个决策 Agent 与 Judge；Agent 通过模型路由调用快/慢模型，通过 MCP 查工具，通过 VectorStore 召回知识库；状态和事件写入业务库。

## 项目结构与模块组织

目标后端结构：

- `app/core/`：配置、LLM 路由与 stub 开关。
- `app/schemas/`：Pydantic 模型，包括决策源和 API 请求/响应。
- `app/engine/`：状态机、纯函数节点、评分和推演编排。
- `app/agents/`：市场、环境、个人、风险 Agent，以及 Simulation Judge Agent。
- `app/api/`：FastAPI 路由与 SSE 流式接口。
- `app/kb/`：决策知识库 ingest、retrieve 与事实校验。
- `app/db/`：SQLAlchemy 模型、会话管理与 VectorStore 抽象。
- `app/mcp_server/`：MCP server 与外部查询工具。
- `scenarios/`：决策源 JSON；这是数据，不是代码。
- `tests/`：与模块对应的 pytest 测试。

目标前端结构：

- `src/api/`：后端 HTTP 调用与 SSE 流式封装。
- `src/views/`：`LibraryView`、`SimView`、`CompareView`、`ProfileView` 等页面。
- `src/components/`：决策表单、时间线、Agent 状态卡、评分面板、风险清单、行动计划和干预卡。
- `src/stores/`：Pinia 状态，管理场景、模拟进度和用户画像。
- `src/three/`：Three.js 分支时间线可视化。

## 构建、测试与开发命令

使用本地虚拟环境，禁止全局安装项目依赖。

- `python -m venv .venv`：创建虚拟环境。
- `.venv\Scripts\Activate.ps1`：在 Windows PowerShell 中激活环境。
- `pip install -e ".[dev]"`：在 `pyproject.toml` 存在后安装项目和开发依赖。
- `pytest`：运行完整测试集。
- `uvicorn app.main:app --reload`：启动本地开发服务。
- `npm install`：在前端工程初始化后安装依赖。
- `npm run dev`：启动 Vue/Vite 前端开发服务。
- `npm run build`：构建前端静态产物。

## 架构边界与职责

坚持“决策源驱动、LLM 只做生成层”。`scenarios/*.json` 决定场景事实、约束和判定规则；LLM 不负责决定关键结局。

`app/engine/nodes.py` 必须保持纯函数，不直接调用 LLM。LLM 调用、短期记忆和工具交互放在 `app/agents/`；评分、风险和结局判定放在 `app/engine/scoring.py`。两层 LangGraph 设计保持清晰：外层负责时间线状态推进，内层负责多 Agent 决策。

## 编码风格与命名约定

Python 使用 4 空格缩进、类型标注和小模块设计。文件、函数、变量、JSON 字段统一使用 `snake_case`。结构化输入输出必须使用 Pydantic 模型，不要用散乱 dict 贯穿核心流程。

System Prompt 与 User Prompt 必须分离。不要把用户原始输入、工具返回或 RAG 片段当作可信指令执行。

## LLM、RAG 与 Agent 红线

模型输出优先使用 `response_format` 或 Function Calling Schema 做协议层约束，不只靠 Prompt 约束。决策推演默认低温（0~0.3）；RAG 场景优先压缩输入，不盲目扩大上下文窗口。

外部工具、检索片段和报错信息回填模型前必须清洗与脱敏。RAG 应保留来源、时间、场景类型等元数据；创业、职业、买房、投资等场景优先做分片 collection 与 `classify_scene` 路由。

Agent 工具优先通过 MCP 暴露。工具 docstring 要写清何时调用、参数类型、取值范围和示例；每个工具都要有超时、必要重试和熔断。关键节点干预使用 LangGraph `interrupt()`，高危或权限不足时切到 `REVIEW` / `PAUSED`。

## 测试规范

测试先行，每个 task 对应 `tests/` 下的测试文件。命名使用 `test_<behavior>.py` 或 `test_<module>.py`，例如 `tests/test_decision_source.py`。优先覆盖 schema 校验、纯节点、Agent stub 路由、评分、人工干预、异常兜底和端到端推演。

## 提交与 Pull Request 规范

当前目录未暴露 Git 历史；提交信息使用简洁英文祈使句，例如 `Add decision source schema`。不要擅自 commit 或 push。

PR 应包含变更摘要、任务背景、测试结果；涉及 UI 原型时附截图。Prompt、模型路由、schema、场景 JSON、评分规则的改动必须单独说明，因为它们会直接影响推演行为。

## 安全与配置建议

API Key 和模型凭证放在环境变量或 `.env`，不要提交到仓库。数据库、文件和外部工具权限遵循最小化原则；写入、删除、涉密接口必须人工确认。异常、超时和无匹配结果应返回统一兜底话术，不暴露原生堆栈。

## 交付自检

- System / User Prompt 是否分离？
- JSON 输出是否有 schema 或协议层约束？
- RAG 内容是否清洗、带来源，并避免 TopK 过大？
- Agent 工具是否最小权限、参数清晰、具备超时和熔断？
- 记忆是否区分短期 checkpointer 与长期 store？
- 是否补齐对应测试，并运行 `pytest`？
