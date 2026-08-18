"""app/kb/ 模块单元测试 —— 覆盖 splitter / chroma / retriever。"""

import pytest

from app.kb.chroma_store import ChromaStore
from app.kb.retriever import HybridRetriever
from app.kb.splitter import load_and_split
from app.scenarios.loader import ScenarioLoader


# ========================================================================== splitter

class TestSplitter:
    def test_loads_all_docs(self):
        chunks = load_and_split("文档种子数据")
        assert len(chunks) >= 20, f"expected >=20 chunks, got {len(chunks)}"
        types = {c.metadata.get("knowledge_type") for c in chunks if c.metadata}
        assert types, "no metadata extracted"
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids)), "duplicate chunk ids"

    def test_skips_readme(self):
        chunks = load_and_split("文档种子数据")
        readme_chunks = [c for c in chunks if "README" in c.chunk_id]
        assert not readme_chunks, "README.md should be skipped"

    def test_chunk_content_not_empty(self):
        chunks = load_and_split("文档种子数据")
        for c in chunks:
            assert c.content.strip(), f"empty chunk: {c.chunk_id}"

    def test_directory_structure_becomes_domain_and_scenario_metadata(self):
        chunks = load_and_split("文档种子数据")

        grad_exam_chunks = [
            chunk for chunk in chunks if chunk.metadata.get("scenario_id") == "grad_exam"
        ]
        assert grad_exam_chunks
        assert {chunk.metadata.get("domain") for chunk in grad_exam_chunks} == {
            "education"
        }
        assert any(chunk.metadata.get("source") for chunk in grad_exam_chunks)

    def test_seed_knowledge_covers_every_shipped_scenario(self):
        chunks = load_and_split("文档种子数据")
        covered_scenarios = {
            str(chunk.metadata.get("scenario_id"))
            for chunk in chunks
            if chunk.metadata.get("scenario_id")
        }
        shipped_scenarios = set(ScenarioLoader("scenarios").list_all())

        assert shipped_scenarios <= covered_scenarios


# ========================================================================== chroma

class TestChromaStore:
    @pytest.fixture(autouse=True)
    def _store(self, tmp_path):
        persist_dir = str(tmp_path / "chroma_test")
        self.store = ChromaStore(persist_dir=persist_dir)
        self.store.delete_collection()
        yield
        try:
            self.store.delete_collection()
        except Exception:
            pass
        self.store.close()

    def test_add_and_count(self):
        assert self.store.count() == 0
        self.store.add(
            ids=["a", "b"],
            documents=["doc a", "doc b"],
            embeddings=[[0.1] * 1024, [0.2] * 1024],
            metadatas=[{"t": "x"}, {"t": "y"}],
        )
        assert self.store.count() == 2

    def test_search_returns_metadata(self):
        self.store.add(
            ids=["k1"],
            documents=["茶饮行业毛利率约65%"],
            embeddings=[[0.1] * 1024],
            metadatas=[{"knowledge_type": "financial_model"}],
        )
        results = self.store.search([0.1] * 1024, top_k=1)
        assert len(results) == 1
        assert results[0]["id"] == "k1"
        assert "65%" in results[0]["document"]

    def test_search_with_where_filter(self):
        self.store.add(
            ids=["x1", "x2"],
            documents=["a", "b"],
            embeddings=[[0.1] * 1024, [0.2] * 1024],
            metadatas=[{"cat": "A"}, {"cat": "B"}],
        )
        results = self.store.search([0.1] * 1024, top_k=5, where={"cat": "A"})
        assert len(results) == 1
        assert results[0]["id"] == "x1"

    def test_delete_collection_clears(self):
        self.store.add(
            ids=["z"], documents=["x"], embeddings=[[0.1] * 1024],
            metadatas=[{"_": "x"}],
        )
        assert self.store.count() == 1
        self.store.delete_collection()
        assert self.store.count() == 0


# ========================================================================== retriever (BM25 + RRF only, no API)

class TestRetrieverLocal:
    @pytest.fixture(autouse=True)
    def _ret(self, tmp_path):
        persist_dir = str(tmp_path / "chroma_ret_test")
        self.store = ChromaStore(persist_dir=persist_dir)
        self.store.delete_collection()
        self.ret = HybridRetriever(store=self.store)
        yield
        try:
            self.store.delete_collection()
        except Exception:
            pass
        self.store.close()

    def test_bm25_rebuild_and_search(self):
        self.store.add(
            ids=["d1", "d2"],
            documents=[
                "新茶饮首年存活率约40% 产品差异化是核心壁垒",
                "杭州餐饮创业补贴最高5万元 食品安全抽检每季度一次",
            ],
            embeddings=[[0.1] * 1024, [0.2] * 1024],
            metadatas=[{"type": "industry"}, {"type": "policy"}],
        )
        self.ret.rebuild_bm25()
        results = self.ret.search("杭州食品安全政策")
        assert len(results) >= 1
        # 至少有一个结果包含相关政策关键词
        all_docs = " ".join(r["document"] for r in results)
        assert "食品安全" in all_docs or "政策" in all_docs or "杭州" in all_docs

    def test_rrf_fusion_dedup(self):
        self.store.add(
            ids=["dup1"],
            documents=["奶茶毛利率65%至70% 人效目标3万元每月"],
            embeddings=[[0.1] * 1024],
            metadatas=[{"_": "dup"}],
        )
        self.ret.rebuild_bm25()
        results = self.ret.search("奶茶毛利率", top_k=3, vector_top=5, bm25_top=5)
        ids = [r["id"] for r in results]
        assert len(ids) == len(set(ids)), f"duplicate ids in results: {ids}"

    def test_empty_store_returns_empty(self):
        self.ret.rebuild_bm25(["占位文档"])
        results = self.ret.search("奶茶")
        assert len(results) <= 1  # 可能返回占位文档或空

    def test_embedding_failure_falls_back_to_local_chinese_bm25(self):
        class FailingEmbedder:
            def embed_query(self, query):
                raise TimeoutError("embedding timeout")

        self.store.add(
            ids=["policy"],
            documents=["美国留学签证政策需要关注申请材料和预约时间"],
            embeddings=[[0.1] * 1024],
            metadatas=[{"scenario_id": "study_abroad"}],
        )
        retriever = HybridRetriever(store=self.store, embedder=FailingEmbedder())

        results = retriever.search(
            "美国留学签证政策",
            where={"scenario_id": "study_abroad"},
        )

        assert results
        assert results[0]["id"] == "policy"

    def test_search_filters_vector_and_bm25_results_by_scenario(self):
        self.store.add(
            ids=["milk-tea", "grad-exam"],
            documents=["奶茶店需要控制原料损耗", "考研需要根据目标院校制定备考计划"],
            embeddings=[[0.1] * 1024, [0.1] * 1024],
            metadatas=[
                {"scenario_id": "milktea_startup"},
                {"scenario_id": "grad_exam"},
            ],
        )
        self.ret.rebuild_bm25()

        results = self.ret.search(
            "备考计划",
            where={"scenario_id": "grad_exam"},
        )

        assert results
        assert all(
            result["metadata"].get("scenario_id") == "grad_exam"
            for result in results
        )


# ========================================================================== classify_scene


class TestClassifyScene:
    """场景分类路由测试。"""

    def test_keyword_match_entrepreneurship(self):
        from app.kb.classify_scene import classify_scene
        assert classify_scene("我想在杭州开一家奶茶店") == "entrepreneurship"

    def test_keyword_match_career(self):
        from app.kb.classify_scene import classify_scene
        assert classify_scene("考虑转行跳槽") == "career"

    def test_keyword_match_housing(self):
        from app.kb.classify_scene import classify_scene
        assert classify_scene("现在买房合适吗") == "housing"

    def test_keyword_match_investment(self):
        from app.kb.classify_scene import classify_scene
        assert classify_scene("定投基金怎么选") == "investment"

    def test_no_match_fallback_general(self):
        from app.kb.classify_scene import classify_scene
        assert classify_scene("今天天气很好") == "general"

    def test_llm_fallback_classifies(self):
        """提供 LLM 时，关键词未命中时走 LLM 分类。"""
        from unittest.mock import MagicMock
        from app.kb.classify_scene import classify_scene

        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "career"
        mock_llm.invoke.return_value = mock_resp

        result = classify_scene("some ambiguous career-related query", llm=mock_llm)
        assert result == "career"
        mock_llm.invoke.assert_called_once()

    def test_llm_invalid_output_fallback(self):
        """LLM 返回无效 domain → fallback general。"""
        from unittest.mock import MagicMock
        from app.kb.classify_scene import classify_scene

        mock_llm = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = "gibberish"
        mock_llm.invoke.return_value = mock_resp

        result = classify_scene("cryptic query", llm=mock_llm)
        assert result == "general"

    def test_llm_json_output_classifies_scene(self):
        from unittest.mock import MagicMock
        from app.kb.classify_scene import classify_scene

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(
            content='{"domain":"education"}'
        )

        assert classify_scene("a cryptic school decision", llm=mock_llm) == "education"

    def test_keyword_match_skips_llm(self):
        """关键词命中时不调 LLM。"""
        from unittest.mock import MagicMock
        from app.kb.classify_scene import classify_scene

        mock_llm = MagicMock()
        result = classify_scene("奶茶店创业", llm=mock_llm)
        assert result == "entrepreneurship"
        mock_llm.invoke.assert_not_called()
