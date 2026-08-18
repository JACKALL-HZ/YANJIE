"""Agent 记忆向量化测试 — embed + Chroma 存储 + 跨会话检索"""
import json

import pytest

from app.kb.chroma_store import ChromaStore
from app.kb.embedder import SiliconFlowEmbedder


@pytest.fixture
def chroma_store(tmp_path):
    """隔离 Chroma 实例（每个测试独立 collection）"""
    import uuid
    store = ChromaStore(
        persist_dir=str(tmp_path / "chroma_mem"),
        collection_name=f"test_agent_mem_{uuid.uuid4().hex[:8]}",
    )
    yield store
    try:
        store.delete_collection()
    except Exception:
        pass


@pytest.fixture
def embedder():
    """真实的 SiliconFlow embedder — 但测试中不实际调 API，mock 它。"""
    from unittest.mock import MagicMock
    mock = MagicMock(spec=SiliconFlowEmbedder)
    mock.embed_query.return_value = [0.1] * 1024
    mock.embed.return_value = [[0.1] * 1024]
    return mock


class TestAgentMemoryStore:
    def test_save_and_search(self, chroma_store, embedder):
        """保存记忆后可通过向量检索找回"""
        from app.kb.agent_memory_store import AgentMemoryStore

        store = AgentMemoryStore(chroma=chroma_store, embedder=embedder)

        store.save(
            user_id="u1",
            agent_id="market",
            domain="奶茶",
            key="prev_decision",
            value_text="上次选了差异化策略，客流量增加但现金消耗快",
        )

        results = store.search(user_id="u1", query="现金消耗太快怎么办", top_k=3)
        assert len(results) > 0
        # 应命中我们刚存的记忆
        assert any("差异化" in r["value_text"] for r in results)

    def test_search_scoped_by_user(self, chroma_store, embedder):
        """检索只在同一 user 范围内"""
        from app.kb.agent_memory_store import AgentMemoryStore

        store = AgentMemoryStore(chroma=chroma_store, embedder=embedder)

        store.save("u1", "market", "奶茶", "k1", "user1的决策")
        store.save("u2", "market", "奶茶", "k1", "user2的决策")

        # u1 检索不应返回 u2 的结果
        results = store.search("u1", "决策")
        texts = [r["value_text"] for r in results]
        assert any("user1" in t for t in texts), f"Should find u1 in {texts}"

    def test_save_overwrites_same_key(self, chroma_store, embedder):
        """同一 key 覆盖写入"""
        from app.kb.agent_memory_store import AgentMemoryStore

        store = AgentMemoryStore(chroma=chroma_store, embedder=embedder)

        store.save("u1", "market", "奶茶", "k1", "版本1")
        store.save("u1", "market", "奶茶", "k1", "版本2")

        results = store.search("u1", "版本")
        texts = [r["value_text"] for r in results]
        # 应该只有版本2
        assert any("版本2" in t for t in texts)

    def test_empty_search_graceful(self, chroma_store, embedder):
        """空库检索不抛异常"""
        from app.kb.agent_memory_store import AgentMemoryStore

        store = AgentMemoryStore(chroma=chroma_store, embedder=embedder)
        results = store.search("nobody", "random query")
        assert isinstance(results, list)
        assert len(results) == 0

    def test_delete_by_domain(self, chroma_store, embedder):
        """按 domain 删除"""
        from app.kb.agent_memory_store import AgentMemoryStore

        store = AgentMemoryStore(chroma=chroma_store, embedder=embedder)

        store.save("u1", "market", "domain_a", "k1", "属于A")
        store.save("u1", "market", "domain_b", "k2", "属于B")

        store.delete_by_domain("u1", "market", "domain_a")

        results = store.search("u1", "属于")
        texts = [r["value_text"] for r in results]
        assert not any("属于A" in t for t in texts)
        assert any("属于B" in t for t in texts)
