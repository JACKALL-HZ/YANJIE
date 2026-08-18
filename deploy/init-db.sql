-- 生产库初始化：启用 pgvector 扩展（向量库切换 pgvector 时使用，当前应用仍用 Chroma）
CREATE EXTENSION IF NOT EXISTS vector;
