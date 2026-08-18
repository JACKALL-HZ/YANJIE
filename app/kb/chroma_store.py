"""Chroma 向量存储 —— VectorStore 协议的本地文件实现。

开发期用 Chroma PersistentClient（SQLite 本地文件），生产期换 pgvector。
"""

import os
from typing import override

import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from chromadb.config import Settings as ChromaSettings

from app.kb.vector_store import VectorStore


class _PassthroughEmbedding(EmbeddingFunction):
    """占位 embedding function：外部已生成向量，Chroma 不重复计算。"""

    def __init__(self) -> None:
        pass

    def name(self) -> str:
        return "passthrough"

    def get_config(self) -> dict:
        return {}

    @override
    def __call__(self, input: Documents) -> Embeddings:
        # 不会被 Chroma 调用——add 时直接传 embeddings 参数
        raise NotImplementedError("use add(embeddings=...) directly")


class ChromaStore(VectorStore):
    """Chromadb 本地持久化实现。

    集合名 decision_kb，持久化目录 chroma_db/。
    """

    COLLECTION = "decision_kb"

    def __init__(self, persist_dir: str | None = None, collection_name: str = "decision_kb") -> None:
        path = persist_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "chroma_db"
        )
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(
            path=path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=_PassthroughEmbedding(),
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------ VectorStore

    @override
    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]],
    ) -> None:
        if not ids:
            return
        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    @override
    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]],
    ) -> None:
        if not ids:
            return
        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    @override
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        where: dict[str, str] | None = None,
    ) -> list[dict]:
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[dict] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0] or []
        metas = results.get("metadatas", [[]])[0] or []
        dists = results.get("distances", [[]])[0] or []
        for idx, cid in enumerate(ids):
            hits.append({
                "id": cid,
                "document": docs[idx] if idx < len(docs) else "",
                "metadata": metas[idx] if idx < len(metas) else {},
                "distance": dists[idx] if idx < len(dists) else 1.0,
            })
        return hits

    @override
    def get_all(self) -> dict:
        """返回全部文档（不含向量，给 BM25 重建索引用）。

        Returns:
            {"ids": [...], "documents": [...], "metadatas": [...]}
        """
        return self._collection.get(include=["documents", "metadatas"])

    @override
    def count(self) -> int:
        return self._collection.count()

    @override
    def delete(self, ids: list[str]) -> None:
        """按 ID 列表删除文档。"""
        if ids:
            self._collection.delete(ids=ids)

    @override
    def delete_collection(self) -> None:
        self._client.delete_collection(name=self._collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=_PassthroughEmbedding(),
            metadata={"hnsw:space": "cosine"},
        )

    def close(self) -> None:
        """释放 Chroma 文件锁（测试 teardown 必须调用）。"""
        # Chroma PersistentClient 无显式 close API；删除引用让 GC 释放
        self._collection = None  # type: ignore[assignment]
        self._client = None  # type: ignore[assignment]
