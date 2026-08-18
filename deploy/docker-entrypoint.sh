#!/bin/sh
# 后端启动脚本：等数据库就绪 → 建表 → 尽力灌知识库 → 起服务
set -e

DB_HOST="${DB_HOST:-db}"
DB_USER="${POSTGRES_USER:-yanjie}"

echo "[entrypoint] waiting for postgres ${DB_HOST}:5432 ..."
until pg_isready -h "${DB_HOST}" -U "${DB_USER}" >/dev/null 2>&1; do
  sleep 1
done
echo "[entrypoint] postgres is ready"

echo "[entrypoint] ensuring business tables ..."
python -c "from app.db import init_db; init_db()"
echo "[entrypoint] tables ok"

echo "[entrypoint] ingesting knowledge base (best-effort) ..."
# 知识库需要 EMBEDDING_API_KEY；失败不应阻断服务启动
python -c "from app.kb.ingest import run_ingest; run_ingest()" \
  || echo "[entrypoint] KB ingest failed (missing EMBEDDING_API_KEY or network) — continuing without RAG corpus"

echo "[entrypoint] starting uvicorn ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
