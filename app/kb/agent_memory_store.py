"""Agent 记忆向量存储。

基于 Chroma 持久化，支持按 user_id 隔离的向量检索。
每次 save() 自动 embed + upsert 到 Chroma collection。
"""

import json

from app.kb.chroma_store import ChromaStore
from app.kb.embedder import SiliconFlowEmbedder


class AgentMemoryStore:
    """Agent 记忆向量存储：embed value → Chroma → 余弦检索。"""

    def __init__(
        self,
        chroma: ChromaStore,
        embedder: SiliconFlowEmbedder,
    ):
        self._chroma = chroma
        self._embedder = embedder

    # ── 公共 API ────────────────────────────────────────

    def save(
        self,
        user_id: str,
        agent_id: str,
        domain: str,
        key: str,
        value_text: str,
    ) -> None:
        """保存/覆盖一条记忆。"""
        mem_id = f"{user_id}:{agent_id}:{domain}:{key}"
        embedding = self._embedder.embed_query(value_text)

        self._chroma.upsert(
            ids=[mem_id],
            embeddings=[embedding],
            documents=[value_text],
            metadatas=[{
                "user_id": user_id,
                "agent_id": agent_id,
                "domain": domain,
                "key": key,
            }],
        )

    def search(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """按 user_id 过滤的语义检索。"""
        if self._chroma.count() == 0:
            return []

        embedding = self._embedder.embed_query(query)
        raw = self._chroma.search(
            query_embedding=embedding,
            top_k=max(top_k * 3, 10),  # 多召回一些用于 user 过滤
        )

        # 过滤 user_id + 截断
        results: list[dict] = []
        for r in raw:
            meta = r.get("metadata", {})
            if meta.get("user_id") != user_id:
                continue
            results.append({
                "id": r.get("id", ""),
                "user_id": meta.get("user_id", ""),
                "agent_id": meta.get("agent_id", ""),
                "domain": meta.get("domain", ""),
                "key": meta.get("key", ""),
                "value_text": r.get("document", ""),
                "distance": r.get("distance", 1.0),
            })
            if len(results) >= top_k:
                break

        return results

    def delete_by_domain(
        self,
        user_id: str,
        agent_id: str,
        domain: str,
    ) -> None:
        """删除指定 domain 下的所有记忆。"""
        all_data = self._chroma.get_all()
        ids_to_delete = []
        for i, mid in enumerate(all_data.get("ids", [])):
            meta = all_data.get("metadatas", [])[i] if i < len(all_data.get("metadatas", [])) else {}
            if (
                meta.get("user_id") == user_id
                and meta.get("agent_id") == agent_id
                and meta.get("domain") == domain
            ):
                ids_to_delete.append(mid)

        if ids_to_delete:
            self._chroma.delete(ids_to_delete)

    def count(self) -> int:
        return self._chroma.count()
