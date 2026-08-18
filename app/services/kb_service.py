"""知识库业务逻辑 —— 检索、ingest、BM25 重建。"""

from app.core.config import Settings
from app.core.logging import get_logger
from app.kb.chroma_store import ChromaStore
from app.kb.embedder import SiliconFlowEmbedder
from app.kb.ingest import run_ingest
from app.kb.retriever import HybridRetriever

logger = get_logger(__name__)


class KbService:
    """知识库业务编排。

    职责：封装检索/ingest/BM25 重建链路，供 API 和 MCP Server 共用。
    """

    def __init__(
        self,
        retriever: HybridRetriever | None = None,
        store: ChromaStore | None = None,
        embedder: SiliconFlowEmbedder | None = None,
        settings: Settings | None = None,
    ):
        self._retriever = retriever
        self._store = store or ChromaStore()
        self._embedder = embedder
        self._settings = settings

    @property
    def retriever(self) -> HybridRetriever | None:
        return self._retriever

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """检索决策知识库，返回 top-k 文档片段。"""
        if self._retriever is None:
            logger.warning("KbService.search called without retriever")
            return []
        return self._retriever.search(query, top_k=top_k)

    def ingest(self, doc_dir: str | None = None) -> int:
        """执行完整 ingest 管道：加载 → 切分 → embed → 双写（Chroma + SQL）。

        返回入库 chunk 数量。
        """
        return run_ingest(
            doc_dir=doc_dir,
            store=self._store,
            embedder=self._embedder,
        )

    def rebuild_bm25(self) -> None:
        """重建 BM25 索引（ingest 后调用）。"""
        if self._retriever is None:
            logger.warning("KbService.rebuild_bm25 called without retriever")
            return
        self._retriever.rebuild_bm25()
