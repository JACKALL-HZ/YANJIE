"""VectorStore 抽象层 —— AGENTS.md 要求切换 Chroma/pgvector 的统一接口。"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class VectorStore(Protocol):
    """决策知识库向量存储抽象。

    方法签名对齐 Chroma / pgvector / Milvus，上层 retriever 只依赖此协议。
    """

    def add(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]],
    ) -> None:
        """批量写入 chunk + 向量 + metadata（不幂等，重复 ID 报错）。"""
        ...

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str]],
    ) -> None:
        """批量写入/覆盖 chunk（幂等，重复 ID 覆盖）。"""
        ...

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        where: dict[str, str] | None = None,
    ) -> list[dict]:
        """纯向量相似度搜索，返回 [{id, document, metadata, distance}]。"""
        ...

    def get_all(self) -> dict:
        """返回全部文档（不含向量），返回 {"ids": [...], "documents": [...], "metadatas": [...]}。"""
        ...

    def count(self) -> int:
        """已入库 chunk 数量。"""
        ...

    def delete_collection(self) -> None:
        """清空 collection（仅开发/测试用）。"""
        ...

    def delete(self, ids: list[str]) -> None:
        """按 ID 列表删除文档。"""
        ...
