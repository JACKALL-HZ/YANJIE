"""混合检索引擎：向量 + BM25 → RRF 融合 → Reranker 重排。

管道：
  1. bge-m3 向量召回 top-20
  2. BM25 关键词召回 top-20
  3. RRF (Reciprocal Rank Fusion) 合并去重
  4. bge-reranker-v2-m3 重排 → 返回 top-k
"""

import httpx
import re

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
from app.kb.chroma_store import ChromaStore
from app.kb.embedder import SiliconFlowEmbedder


class HybridRetriever:
    """混合检索 + Reranker，对外暴 search(query) → top-k chunk 列表。"""

    def __init__(
        self,
        store: ChromaStore | None = None,
        embedder: SiliconFlowEmbedder | None = None,
    ) -> None:
        self.store = store or ChromaStore()
        if embedder is not None:
            self.embedder = embedder
        else:
            config = get_settings().embedding
            self.embedder = SiliconFlowEmbedder(config) if config.api_key else None
        self._bm25_records: list[dict] = []
        self._bm25 = None          # rank_bm25.BM25Okapi，懒加载
        self._bm25_docs: list[str] = []  # BM25 索引用的文档列表

    # ------------------------------------------------------------------- 公开 API

    def search(
        self,
        query: str,
        top_k: int = 5,
        vector_top: int = 20,
        bm25_top: int = 20,
        rrf_k: int = 60,
        where: dict[str, str] | None = None,
    ) -> list[dict]:
        """混合检索 + reranker 重排。

        Returns:
            [{id, document, metadata, score}] 按 reranker score 降序
        """
        # 1. 向量召回。Embedding 服务不可用时保留 BM25 路径，
        # 知识库仍可按本地关键词返回结果，不让外部网络故障阻断推演。
        vec_hits: list[dict] = []
        if self.embedder is not None:
            try:
                query_emb = self.embedder.embed_query(query)
                vec_hits = self.store.search(query_emb, top_k=vector_top, where=where)
            except Exception as exc:
                logger.warning("embedding retrieval failed, using BM25 fallback: %s", type(exc).__name__)

        # 2. BM25 召回
        bm25_hits = self._bm25_search(query, top_k=bm25_top, where=where)

        # 3. RRF 融合
        fused = self._rrf_fuse(vec_hits, bm25_hits, k=rrf_k)

        # 4. Reranker 重排
        if len(fused) <= top_k:
            return fused[:top_k]
        return self._rerank(query, fused, top_k=top_k)

    def rebuild_bm25(self, documents: list[str] | None = None) -> None:
        """重建 BM25 索引（ingest 后调用一次）。

        若不传 documents，则从 Chroma 全量拉取。
        """
        from rank_bm25 import BM25Okapi
        if documents is None:
            all_data = self.store.get_all()
            documents = all_data.get("documents") or []
            ids = all_data.get("ids") or []
            metadatas = all_data.get("metadatas") or []
            self._bm25_records = [
                {
                    "id": ids[index] if index < len(ids) else f"bm25-{index}",
                    "document": document,
                    "metadata": metadatas[index] if index < len(metadatas) else {},
                }
                for index, document in enumerate(documents)
            ]
        else:
            self._bm25_records = [
                {"id": f"bm25-{index}", "document": document, "metadata": {}}
                for index, document in enumerate(documents)
            ]
        self._bm25_docs = documents
        if not documents:
            self._bm25 = None
            return
        tokenized = [self._tokenize(doc) for doc in documents]
        self._bm25 = BM25Okapi(tokenized)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """同时支持中文单字、英文词和数字，避免中文整句无法命中 BM25。"""
        return re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())

    # ------------------------------------------------------------------- 内部

    def _bm25_search(
        self, query: str, top_k: int, where: dict[str, str] | None = None
    ) -> list[dict]:
        if self._bm25 is None:
            self.rebuild_bm25()
        if not self._bm25_docs or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(self._tokenize(query))
        # 取 top_k
        ranked = sorted(
            (
                (index, score)
                for index, score in enumerate(scores)
                if where is None
                or all(
                    self._bm25_records[index]["metadata"].get(key) == value
                    for key, value in where.items()
                )
            ),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]
        return [
            {
                "id": self._bm25_records[idx]["id"],
                "document": self._bm25_docs[idx],
                "metadata": self._bm25_records[idx]["metadata"],
                "score": float(s),
            }
            for idx, s in ranked
        ]

    @staticmethod
    def _rrf_fuse(
        vec_hits: list[dict],
        bm25_hits: list[dict],
        k: int = 60,
    ) -> list[dict]:
        """RRF 融合：按文档内容去重，合并两个列表的排名分数。"""
        seen: dict[str, dict] = {}  # document -> merged hit
        for rank, hit in enumerate(vec_hits):
            doc = hit["document"]
            if doc not in seen:
                seen[doc] = {**hit, "score": 1.0 / (k + rank + 1)}
            else:
                seen[doc]["score"] += 1.0 / (k + rank + 1)
        for rank, hit in enumerate(bm25_hits):
            doc = hit["document"]
            if doc not in seen:
                seen[doc] = {**hit, "score": 1.0 / (k + rank + 1)}
            else:
                seen[doc]["score"] += 1.0 / (k + rank + 1)
        fused = list(seen.values())
        fused.sort(key=lambda h: h["score"], reverse=True)
        return fused

    def _rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        """调硅基流动 bge-reranker-v2-m3 重排。"""
        settings = get_settings()
        base = settings.embedding.base_url.rstrip("/")
        headers = {
            "Authorization": f"Bearer {settings.embedding.api_key}",
            "Content-Type": "application/json",
        }
        documents = [c["document"] for c in candidates]
        payload = {
            "model": "BAAI/bge-reranker-v2-m3",
            "query": query,
            "documents": documents,
            "top_n": top_k,
        }
        try:
            resp = httpx.post(
                f"{base}/rerank",
                json=payload,
                headers=headers,
                timeout=get_settings().embedding.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            return [
                {**candidates[r["index"]], "score": r["relevance_score"]}
                for r in results
                if r["index"] < len(candidates)
            ]
        except httpx.HTTPError as e:
            # Reranker 挂了就降级返回 RRF 融合结果
            logger.warning("reranker API error, falling back to RRF: %s", e)
            return candidates[:top_k]
