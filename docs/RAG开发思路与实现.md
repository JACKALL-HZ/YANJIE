# 衍界 YanJie AI · RAG 开发思路与实现说明

> 定位：本文整理本项目的 RAG（检索增强生成）模块**设计思想与实现落点**，供后续维护、扩展知识库、排查检索问题时对照代码使用。
> 范围：聚焦「文档入库（ingestion）」与「检索（retrieval）」两阶段中**元数据/标签体系**的设计思路，附带加载与切分策略。
> 代码基线：2026-08-05；核心代码位于 `app/kb/`。

---

## 1. RAG 整体三阶段视图

标准 RAG 拆成三个阶段，本项目当前已实现前两段（生成段的"把检索结果回填模型"在 `app/agents/` 侧完成）：

```
① 索引/入库 (ingestion)  ──→  ② 检索 (retrieval)  ──→  ③ 生成 (generation)
   加载→打标→切分→向量化→写库      语义召回 + 标签过滤        检索片段回填 LLM
   （离线、一次性）              （在线、每次推演）         （LLM 只做生成层）
```

**关键思想：元数据/标签是在第①阶段（入库时）打好的，之后第②阶段检索只是"刷胸牌进门"，不再现造标签、也不再调模型去分类。**

---

## 2. 文档加载（Ingestion · Load）

入口：`app/kb/ingest.py` → `run_ingest()`，默认扫描目录为项目根的 **`文档种子数据/`**（中文目录名）。

加载逻辑（`app/kb/splitter.py:65` `load_and_split()`）：

- **递归扫描**：`Path.rglob("*.md")` 遍历目录下所有 Markdown。
- **跳过规则**：`README.md` 与路径中含 `archive` 的目录不参与。
- **读取方式**：`fpath.open(encoding="utf-8")` 整文件读为字符串，不做二进制/PDF/Word 解析。
- **当前局限**：仅支持 Markdown 纯文本。

**思想**：加载是"无脑收件"，不在此阶段理解内容，只为后续切分与打标提供原始文本。

---

## 3. 切分策略（Split）

切分器（`app/kb/splitter.py:21`）：

```python
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600, chunk_overlap=80,
    separators=_MD_SEPARATORS, keep_separator=True,
)
```

- 分隔符优先级：**Markdown 结构优先** —— `## / ###` 标题 → 空行段落 → `。；，` 标点 → 空格。
- 每块 600 字符，相邻块重叠 80 字符，避免切到句子中间丢失上下文。
- `keep_separator=True` 保留分隔符，保留结构语义。

**思想**：切分不破坏语义边界（优先按标题/标点断），保证每个 chunk 是"可读的语义单位"，而非生硬截断。

---

## 4. 元数据与标签体系（核心思想）

### 4.1 打标签在哪个阶段

在 `load_and_split()` 内部，**读取之后、切分之前**完成：

```
raw = f.read()                       # ① 读取
meta = _parse_frontmatter(raw)      # ② 打标签（文档内 + 目录推导）
#   meta 此时挂在"整篇文档"上
texts = _splitter.split_text(raw)   # ③ 切分
for text in texts:
    DocChunk(content=text, metadata=dict(meta))   # ④ 每块继承同一份 meta
```

- 标签是**文档级（document-level）定义一次**，切分后每个 chunk **拷贝继承**同一份 `metadata`。
- 例：一篇 3000 字资料切成 5 块，5 块的 `scenario_id`/目录标签完全相同。

### 4.2 标签的两类来源

| 来源 | 代码位置 | 内容 | 是否必须手写 |
|---|---|---|---|
| A. 文档内 frontmatter | `splitter.py:37` `_parse_frontmatter()` | YAML 头（`---` 块）+ `>` 引用注释行 | 是（可选） |
| B. 目录结构推导 | `splitter.py:76-78` | `scenario_id` / `domain` | 否（放对文件夹即自动） |

- **来源 A（手写）**：文档开头写 `---` YAML 块，或正文里写 `> 知识类型：政策` 这类引用行。`_parse_frontmatter` 把中文 key 归一化：
  `知识类型→knowledge_type`、`覆盖城市→city`、`适用场景→scenario`、`用途→usage`、`说明→note`。
- **来源 B（自动）**：文件相对路径的层级决定：
  ```python
  if len(relative_path.parts) >= 3:
      meta.setdefault("domain", relative_path.parts[0])      # 一级目录
      meta.setdefault("scenario_id", relative_path.parts[1]) # 二级目录
  ```
  即 `文档种子数据/<domain>/<scenario_id>/文件.md` 这种摆放，自动标成对应场景。

> 调用方用 `setdefault`，故来源 A 的标签优先级高于来源 B —— 文档内写了就以文档内为准。

### 4.3 标签如何确定：约定驱动，而非 LLM 生成

**这是本项目 RAG 最重要的设计取舍：标签值 100% 由"目录摆放位置 + 文档内手写"这两个人工约定确定，全程不调用任何模型。**

对应架构红线「决策源驱动、LLM 只做生成层」：

- **好处**：标签可控、零成本、零延迟、可预期、可复现。
- **代价**：标签质量完全依赖资料维护规范。放错目录 / 不写 frontmatter → 标签缺失（但不会报错崩溃）。

> 对比业界另一种做法：用 LLM 自动给文档分类打标。本项目刻意不采用，因其引入不确定性，与"决策源驱动"原则冲突。

### 4.4 元数据的流转位置

```
.md 文件
 └─ 读取 raw
    └─ 打标签 → 局部变量 meta (dict)        【切分前 · 函数栈内存】
       └─ 切分   → 每个 DocChunk.metadata    【切分后 · 内存对象】
          └─ 入库 → Chroma metadatas         【持久化 · 向量库】
                 → SQL kb_chunks 列          【持久化 · 关系表，仅抽取部分字段】
```

- 数据结构定义：`splitter.py:34` `DocChunk.metadata: dict[str, str]`。
- 入库落盘：`ingest.py:58-60` 取 `c.metadata` → `store.add(metadatas=metas)` → `chroma_store.py:73` 写入 Chroma 的 `metadatas`。
- SQL 侧（`ingest.py:62-70`）只抽取 `industry / city / chunk_type / source` 写入 `kb_chunks` 表列，**并非整份 metadata**。

### 4.5 元数据即标签容器

`metadata` 这个 dict 里每对 `key:value` 就是一个标签。两者是同一事物的两面：

- **自动标签（文档不写也有）**：`scenario_id`、`domain`、`source`、`document_title`、`source_file`。
- **手写标签（写了才有）**：`knowledge_type`、`industry`、`city`。

> 比喻：元数据是"快递面单"，正文是包裹内容。没有面单，所有包裹堆一起只能靠内容猜；有面单，先按面单分拣再精细找。

---

## 5. 检索隔离（Retrieval · where 过滤）

检索入口：`app/kb/retriever.py:39` `search(query, where=...)` —— 混合检索（向量召回 + BM25 召回 → RRF 融合 → reranker 重排）。

`where` 参数就是拿 metadata 里的标签做**场景隔离**：

```python
# 向量召回
vec_hits = self.store.search(query_emb, top_k=vector_top, where=where)
# BM25 召回也过同一份 where
bm25_hits = self._bm25_search(query, top_k=bm25_top, where=where)
# 过滤逻辑（retriever.py:110）
self._bm25_records[idx]["metadata"].get(key) == value
```

推演"奶茶创业"场景时传入 `where={"scenario_id": "milktea_startup"}`，保证只在该场景资料内做语义匹配，不混入其他场景。

**思想：先按标签圈定范围，再做语义匹配** —— 这是 RAG 精准召回的关键，而非"一锅粥全文向量相似度"。

---

## 6. 双写存储（Chroma + SQL）

`ingest.py` 每批 `batch_size=10` 同时写两处：

- **Chroma 向量库**：`store.add(ids, documents, embeddings, metadatas)` —— 向量 + 正文 + 元数据一体存储，支撑语义检索与 `where` 过滤。
- **SQL `kb_chunks` 表**：仅抽取 `industry/city/chunk_type/source` 等结构化字段，支撑关系型查询/后台管理。

**思想：向量库负责"语义 + 标签过滤"，关系表负责"结构化字段的精确查询"，二者互补。**

---

## 7. 设计哲学总结

1. **决策源驱动，约定优于 AI 自动分类**：标签由目录结构与手写 frontmatter 确定，LLM 不参与分类，保证可控可预期。
2. **标签在入库时一次性打好，检索时复用**：离线贴标、在线刷标，零运行时开销。
3. **先过滤后匹配**：用 `scenario_id` 等标签做场景隔离，是精准召回的基石。
4. **文档级定义、块级继承**：一篇资料的所有 chunk 共享同一份标签，维护成本低。
5. **目录即配置**：把文件放进正确的 `domain/scenario_id` 文件夹，即完成最关键的环境隔离，无需任何额外标注。

---

## 8. 当前实现备注与待优化

以下为已知可改进点（非阻塞，按需处理）：

- **目录约定脆弱**：`scenario_id` 取自 `relative_path.parts[1]`，目录层级不足 3 级时标签缺失且无告警。建议对缺失 `scenario_id` 的文档在 ingest 时打印警告。
- **frontmatter 解析为手搓简易版**：`startswith("---")` 要求文件首字符即 `---`，前有空行/BOM 即整段失效；不支持嵌套/列表 YAML。文档变复杂时需换用正式 YAML 解析库。
- **BM25 索引未主动重建**：`ingest` 后未调用 `rebuild_bm25()`，首次检索才懒重建且只含当时 Chroma 全量；增量 ingest 后 BM25 可能与向量库不同步（历史 RAG 审查结论）。
- **死代码**：`app/kb/classify_scene.py` 的 `get_collection_for_domain` 分片路由未被调用（历史审查标记），当前隔离完全依赖 `where` 过滤而非分片 collection。
- **资料库规范缺失**：`domain` / `scenario_id` / `industry` 等取值无统一文档约束，多人维护易拼写不一致导致隔离漏检。建议补充《目录与元数据规范》。

---

*整理自 2026-08-05 RAG 代码走查会话。代码位置以实际为准，如行号漂移请以当前文件核对。*
