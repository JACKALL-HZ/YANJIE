# 衍界 YanJie AI · 生产部署包

一键式 `docker compose up` 即可拉起：PostgreSQL(pgvector) + Redis + 后端(FastAPI) + 前端(Nginx)。
前端走相对路径 `/api`，由 Nginx 反代到后端，**无需改前端代码**。

## 目录结构
```
Dockerfile                # 后端镜像（python:3.12-slim）
Dockerfile.frontend       # 前端静态托管镜像（nginx:alpine）
docker-compose.yml        # 编排：db / redis / backend / frontend
.dockerignore
deploy/
  docker-entrypoint.sh    # 后端启动：等DB → 建表 → 灌知识库 → 起 uvicorn
  nginx.conf              # Nginx：静态托管 + /api 反代（SSE 关缓冲）
  init-db.sql             # 启用 pgvector 扩展
  backend.env.example     # 后端环境变量模板
  README.md               # 本文件
```

## 前置条件
- Docker Engine 24+ 与 Docker Compose v2
- 服务器开放 80 端口（或改 `HTTP_PORT`）
- 可用的 DeepSeek API Key、硅基流动 API Key（bge-m3 embedding）

## 快速开始
```bash
# 1. 准备环境变量
cp deploy/backend.env.example deploy/backend.env
# 编辑 deploy/backend.env，至少填：
#   FAST_LLM_API_KEY / SLOW_LLM_API_KEY   DeepSeek
#   EMBEDDING_API_KEY                    硅基流动
#   JWT_SECRET                           见下方生成命令
#   ALLOWED_ORIGINS                      你的域名，例如 https://yanjie.example.com
#   POSTGRES_PASSWORD                    建议改掉默认 yanjie_pw

# 2. 生成 JWT 密钥（>=32 字节随机串）
python -c "import secrets;print(secrets.token_urlsafe(48))"
# 把输出填到 backend.env 的 JWT_SECRET

# 3. 构建并启动
docker compose up -d --build

# 4. 查看状态
docker compose ps
curl http://localhost/api/health      # 应返回健康检查 JSON
```

## 环境变量要点（踩坑提示）
- **两个数据库 URL 格式不同，不能混用：**
  - `DATABASE_URL` 用 SQLAlchemy 格式，必须带 `+psycopg` 方言：
    `postgresql+psycopg://yanjie:密码@db:5432/yanjie`
  - `CHECKPOINTER_URL` 用 LangGraph 原生格式，**不要** `+psycopg`：
    `postgresql://yanjie:密码@db:5432/yanjie`
- `JWT_SECRET` 必须 ≥32 字节，否则后端启动直接报错（已在 `config.py` 强校验）。
- `ALLOWED_ORIGINS` 生产环境禁止填 `*`，必须写具体域名，否则启动报错。
- `LLM_USE_STUB` 生产设 `0`（真实模型）。模型配置错误会导致推演失败。
- `CHROMA_PERSIST_DIR=/app/chroma_data` 已挂卷，知识库持久化不会被容器重建清空。

## 知识库初始化
启动脚本会**自动**执行 `run_ingest()`（把 `文档种子数据/` 切分 → bge-m3 向量化 → 写入 Chroma）。
需要 `EMBEDDING_API_KEY` 与网络。若缺失，脚本会告警但**不阻断启动**——此时 RAG 无语料，推演仍可进行但检索为空。
重新灌库：`docker compose exec backend python -c "from app.kb.ingest import run_ingest; run_ingest()"`

## 验证清单
- [ ] `docker compose ps` 四个服务均 healthy/running
- [ ] `curl http://<服务器IP>/api/health` 返回 200
- [ ] 浏览器打开前端，能注册/登录、能发起一次推演且 SSE 流式返回
- [ ] 知识库已灌入（`docker compose exec backend python -c "from app.kb.chroma_store import ChromaStore; print(ChromaStore().count())"` 应 >0）

## 已知边界与后续项
**当前向量库仍是 Chroma（本地持久化卷），不是 pgvector。**
`deploy/init-db.sql` 已在 PostgreSQL 启用 `vector` 扩展待用，但应用层 `app/kb/chroma_store.py` 尚未实现 `PgVectorStore`。切换需：实现 PgVectorStore + 在 `pyproject` 加 `pgvector` + 改 `engine._build_retriever`。属 P1。

- **P1（上线前应补）**
  - 向量库迁 pgvector（去掉 Chroma 卷依赖，统一数据层）
  - 限流切 Redis 后端（`fastapi-limiter` + Redis，实现按真实客户端 IP 限流；当前为内存全局限流）
  - HTTPS / 域名（Nginx 加 TLS，或前置 CLB/证书）
  - 备份策略（PG 定时 `pg_dump`，chroma_data 卷快照）
- **P2（锦上添花）**
  - 后端容器内降权运行非 root（需给 chroma_data 卷 chown）
  - CI/CD、回滚、监控/日志收集
  - 成本评估：DeepSeek V3/R1 调用量与预算告警
