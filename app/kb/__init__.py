"""app/kb/ —— 决策知识库（Decision Knowledge Base）。

AGENTS.md 红线：VectorStore 抽象层，固定 bge-m3 embedding。

对外暴露：
  - run_ingest()    一键入库种子文档
  - HybridRetriever  混合检索引擎
"""

from app.kb.chroma_store import ChromaStore
from app.kb.embedder import SiliconFlowEmbedder
from app.kb.ingest import run_ingest
from app.kb.retriever import HybridRetriever
from app.kb.vector_store import VectorStore

__all__ = [
    "ChromaStore",
    "HybridRetriever",
    "SiliconFlowEmbedder",
    "VectorStore",
    "run_ingest",
]
