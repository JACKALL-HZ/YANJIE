# 衍界 YanJie AI · CLAUDE.md

> 适用范围：AI 决策推演工作台 MVP-0~2 全周期开发。
> 规范来源：AI 大模型后端开发工程规范 + 项目实际需求裁剪。
> 标准基线：2026-07 当下生产实践。

## 1. 项目概况

AI 决策推演工作台（Decision Simulation Workbench）——覆盖「拆解→建模→推演→对比→风险→行动→复盘→校准」全周期的决策辅助系统。

- **阶段**：MVP-0（纯后端 + Mock LLM stub + 文本时间线）
- **性质**：个人学习项目（面试作品集向），非商业产品
- **技术栈**：Python 3.12 + FastAPI + LangGraph + LangChain + RAG + MCP + pytest
- **参考文档**：`衍界 YanJie AI-PRD-最终优化版.md`（产品定义）、`衍界 YanJie AI-实现计划.md`（任务拆解）

## 2. 架构核心

- **决策源 JSON 驱动**：`scenarios/*.json` 是数据不是代码，LLM 不负责决定剧情关键
- **两层 LangGraph**：外层 8 节点时间线 + 内层 4 节点 Agent 决策
- **引擎纯函数**：`engine/nodes.py` 不调 LLM，LLM 调用委托 `agents/`
- **职责边界**：agents 只调 LLM + 管记忆，不做结局判定；scoring 独立
- **LLM stub 开关**：`app/core/llm.py` 支持 stub 模式断 LLM 跑通判定
- **Agent 工具协议**：优先 MCP（Model Context Protocol）标准化暴露工具

## 3. 目标结构

```
yanjie-ai/
├── pyproject.toml
├── scenarios/            # 决策源 JSON（数据，非代码）
├── app/
│   ├── core/             # config, llm 路由（含 stub 开关）
│   ├── schemas/          # Pydantic 模型（决策源、API 请求/响应）
│   ├── engine/           # 状态机 + 纯函数节点 + 评分
│   ├── agents/           # 4 决策 Agent + Judge + 内层图
│   └── api/              # FastAPI 路由 + SSE
└── tests/                # pytest 测试集
```

## 4. 技术栈与选型约定

- **运行环境**：Python 3.12+；依赖用 venv 隔离，禁止全局 pip install
- **模型选型**：按量云 API（通义/文心/星火/DeepSeek），不限定单一厂商；中文场景优先国产基座
- **Embedding**：中文统一用 bge-zh / m3e / gte-qwen2，文档与查询必须用同一模型，入库前 L2 归一化
- **向量库**：MVP-0 用 Chroma 内存；后续可迁 FAISS / pgvector / Milvus
- **框架**：RAG 数据层用 LlamaIndex 或 LangChain；多步编排 / Agent 用 LangChain + LangGraph
- **Agent 工具协议**：优先 MCP 标准化暴露工具，避免每框架手搓

## 5. 开发红线（Hard Rules）

| 规则 | 原因 |
|---|---|
| System Prompt 与 User Prompt 强制拆分，绝不在业务代码里把两者拼接成一段再发给模型 | 防 Prompt 注入 / 越权篡改 |
| 绝不把用户原始输入当作可信指令；所有外部内容（工具返回、检索片段）回填模型前做清洗与脱敏 | 安全底线 |
| Agent 工具权限最小化：数据库只读；写/删/涉密接口必须人工确认（Human-in-the-loop） | 权限控制 |
| 结构化输出走协议层：JSON 输出用 response_format / Function Calling Schema，不要只靠 Prompt 约束 | 输出稳定性 |
| RAG 检索结果回填模型前做清洗，屏蔽原生报错堆栈 | 用户体验 |

## 6. 大模型调用规范

### 6.1 参数与采样

- `temperature` 与 `top_p` 二选一调，不要同时拉满
- 决策推演（求稳）→ 低温（0~0.3）；创意场景 → 高温（0.7~1.0）
- `max_output_tokens` 限制输出侧，RAG 场景优先压缩输入而非放大窗口

### 6.2 流式与中断

- 对话 / 推演过程必须流式输出（SSE），模拟实时推演
- 用户手动停止 → 后端立即销毁推理上下文、断连、停止计费

### 6.3 异常与兜底

- 一律配重试 + 指数退避 + 熔断；非幂等写操作禁止盲重试
- 任何异常 / 超时 / 无匹配 → 返回标准化兜底话术，屏蔽原生报错堆栈

## 7. RAG 开发规范（决策知识库）

- **分块**：RecursiveCharacterTextSplitter（chunk_size 300~800、overlap 10~20%）；决策模板类用语义分块或父子分块
- **混合检索**：BM25 稀疏 + 向量稠密，RRF 融合（专名/编号场景必上）
- **Rerank 重排**：向量粗召回 top-20 → cross-encoder 精排 top-3~5，解决"中间迷失"
- **TopK**：宁宽召回 + Rerank，勿盲目调大（Prompt 膨胀、token 费）
- **元数据**：随 chunk 存来源 / 时间 / 场景类型；检索用 pre-filter
- **场景化路由**：按创业/职业/买房/投资领域分片独立 collection + `classify_scene` 路由
- **知识库生命周期**：文档绑过期标签，定时任务屏蔽过期向量

## 8. Agent 开发规范

### 8.1 闭环范式

- 单 Agent 走 ReAct（Thought→Action→Observation）
- 长周期复合任务用 Plan-and-Execute（先规划再分步）
- 本项目 4 个决策 Agent（市场/环境/个人/风险）+ Simulation Judge Agent

### 8.2 工具（Tool）

- 用 `@tool` 装饰器，docstring 写清"何时调 + 参数类型 / 取值 / 示例"，描述即契约
- 参数强制 JSON Schema（required / enum 显式声明）
- 优先 MCP Server 暴露，即插即用

### 8.3 记忆分层

- **短期**：checkpointer（回合状态恢复），MVP-0 可用内存，后续接 Redis + TTL
- **长期**：LongTermStore（跨模拟长期记忆），向量库持久化
- 热短期 / 冷长期不混用

### 8.4 稳定性三件套

- 每工具独立超时 → 非幂等禁盲重试 → 连续失败熔断
- 超时转兜底话术

### 8.5 人工接管

- 关键节点干预用 LangGraph `interrupt()` 标准 HITL
- 高危 / 权限不足 / 卡死 → 状态机切 REVIEW/PAUSED
- 配置化阈值，不写死代码

## 9. 推荐代码范式

### 9.1 强制 JSON 结构化输出

```python
resp = client.chat.completions.create(
    model="qwen-plus",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},   # 与 user 严格拆分
        {"role": "user", "content": user_input},
    ],
    response_format={"type": "json_object"},            # 协议层强约束
    temperature=0.2,
)
```

### 9.2 Agent 工具 + 超时熔断

```python
import concurrent.futures as cf
from langchain_core.tools import tool

@tool
def query_decision_kb(query: str, scene: str = "startup") -> str:
    """查询决策知识库。query 必填；scene 可选 startup|career|house|investment。"""
    # ... 实现 ...
    return result

def call_with_timeout(fn, args, timeout=5):
    with cf.ThreadPoolExecutor(1) as ex:
        fut = ex.submit(fn, *args)
        try:
            return fut.result(timeout=timeout)
        except cf.TimeoutError:
            return '{"status":"timeout","data":"工具超时，已切换兜底"}'
```

### 9.3 短期记忆 TTL

```python
# MVP-0 用内存字典，后续接 Redis
import time

_memory_store: dict[str, list] = {}

def save_turn(sid: str, turn: dict, ttl: int = 1800):
    if sid not in _memory_store:
        _memory_store[sid] = []
    _memory_store[sid].append({"data": turn, "expire": time.time() + ttl})
    # 清理过期
    _memory_store[sid] = [t for t in _memory_store[sid] if t["expire"] > time.time()]
```

## 10. 交付 CheckList（提交前自检）

- [ ] System / User Prompt 是否拆分？用户输入是否未被当指令执行？
- [ ] JSON 输出是否走协议层（response_format / Schema）而非纯 Prompt？
- [ ] RAG 是否上了混合检索 + Rerank？TopK 是否过大？元数据是否 pre-filter？
- [ ] Agent 工具描述是否写清参数？权限是否最小化？超时 / 重试 / 熔断是否齐？
- [ ] 记忆是否分层 + TTL？异常是否统一兜底话术？
- [ ] 测试先行，每个 task 对应 `tests/` 下的测试文件

## 11. 开发流程规范

- 测试先行，每个 task 对应 `tests/` 下的测试文件
- Commit message 用简洁英文，符合常规规范
- 不擅自 commit / push
- 修改前先读相关文件，理解上下文
- 最小改动原则，不做无关重构

## 12. 当前任务

按 `衍界 YanJie AI-实现计划.md` 中的 Task 0 起步：项目初始化 → pyproject.toml → 决策源 schema → ...
