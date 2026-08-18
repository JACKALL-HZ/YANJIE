"""Ingest 管道：文档加载 → 切分 → embed → 入库（Chroma + SQL 双写）。

对外暴露 run_ingest()，一键把 文档种子数据/ 灌入 Chroma 和 kb_chunks 表。
"""

import logging
import os

from app.core.config import get_settings
from app.kb.chroma_store import ChromaStore
from app.kb.embedder import SiliconFlowEmbedder
from app.kb.splitter import load_and_split

logger = logging.getLogger(__name__)


def run_ingest(
    doc_dir: str | None = None,
    store: ChromaStore | None = None,
    embedder: SiliconFlowEmbedder | None = None,
    batch_size: int = 10,
) -> int:
    """执行完整 ingest：加载 → 切分 → embed → 写入 Chroma + kb_chunks 表。

    Args:
        doc_dir: 种子文档目录，默认 项目根/文档种子数据
        store: ChromaStore 实例，默认自动创建
        embedder: SiliconFlowEmbedder 实例，默认读 .env 创建
        batch_size: embed 批大小

    Returns:
        入库 chunk 总数
    """
    if doc_dir is None:
        doc_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "文档种子数据"
        )
    if store is None:
        store = ChromaStore()
    if embedder is None:
        settings = get_settings()
        embedder = SiliconFlowEmbedder(settings.embedding)

    chunks = load_and_split(doc_dir)
    if not chunks:
        logger.info("No chunks found — nothing to do")
        return 0

    logger.info("loaded %d chunks from %s", len(chunks), doc_dir)

    # ── 双写：Chroma + SQL ──
    sql_records: list[dict] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = [c.chunk_id for c in batch]
        docs = [c.content for c in batch]
        metas = [c.metadata for c in batch]
        embs = embedder.embed(docs)
        # 可重复执行：目录调整或补充文档后覆盖同 ID chunk，避免 add 导致重复入库失败。
        store.upsert(ids=ids, documents=docs, embeddings=embs, metadatas=metas)

        for c in batch:
            sql_records.append({
                "chunk_id": c.chunk_id,
                "content": c.content,
                "industry": c.metadata.get("industry"),
                "city": c.metadata.get("city"),
                "chunk_type": c.metadata.get("type", "general"),
                "source": c.metadata.get("source", ""),
            })

        logger.info("batch %d: %d chunks embedded", i // batch_size + 1, len(batch))

    # 写入 SQL
    if sql_records:
        from app.db.repository import KbChunkRepo
        from app.db.session import SessionLocal, init_db

        init_db()
        db = SessionLocal()
        try:
            repo = KbChunkRepo(db)
            repo.save_batch(sql_records)
            db.commit()
            logger.info("%d chunks synced to kb_chunks table", len(sql_records))
        except Exception:
            db.rollback()
            logger.warning("SQL sync failed (kb_chunks), Chroma only", exc_info=True)
        finally:
            db.close()

    logger.info("done — %d chunks in Chroma", store.count())
    return store.count()
