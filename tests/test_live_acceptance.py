"""Provider acceptance checks, deliberately disabled for ordinary pytest runs."""

import math
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import EmbeddingConfig, LlmConfig
from app.core.llm import build_llm
from app.kb.chroma_store import ChromaStore
from app.kb.embedder import SiliconFlowEmbedder
from app.kb.retriever import HybridRetriever


def _live_config() -> dict[str, str]:
    """Read local provider settings without mutating the isolated test env."""
    values = dotenv_values(Path(".env"))
    return {
        key: str(values.get(key) or os.getenv(key, ""))
        for key in (
            "FAST_LLM_BASE_URL",
            "FAST_LLM_API_KEY",
            "FAST_LLM_MODEL",
            "FAST_LLM_TIMEOUT",
            "FAST_LLM_MAX_RETRIES",
            "EMBEDDING_BASE_URL",
            "EMBEDDING_API_KEY",
            "EMBEDDING_MODEL",
            "EMBEDDING_TIMEOUT",
            "CHROMA_PERSIST_DIR",
        )
    }


def _require_live_enabled() -> None:
    if os.getenv("YANJIE_RUN_LIVE_TESTS") != "1":
        pytest.skip("set YANJIE_RUN_LIVE_TESTS=1 to run provider acceptance")


@pytest.mark.live
def test_live_embedding_and_hybrid_retrieval_return_scenario_sources():
    _require_live_enabled()
    config = _live_config()
    assert config["EMBEDDING_API_KEY"], "EMBEDDING_API_KEY is required for live acceptance"

    embedder = SiliconFlowEmbedder(
        EmbeddingConfig(
            model=config["EMBEDDING_MODEL"] or "BAAI/bge-m3",
            base_url=config["EMBEDDING_BASE_URL"],
            api_key=config["EMBEDDING_API_KEY"],
            timeout=int(config["EMBEDDING_TIMEOUT"] or 15),
        )
    )
    vector = embedder.embed_query("奶茶创业的现金流和选址风险")
    assert len(vector) >= 256
    assert all(math.isfinite(item) for item in vector)

    store = ChromaStore(persist_dir=config["CHROMA_PERSIST_DIR"] or "chroma_db")
    assert store.count() > 0, "the local decision knowledge base must be ingested"
    hits = HybridRetriever(store=store, embedder=embedder).search(
        "奶茶创业现金流风险",
        top_k=1,
        where={"scenario_id": "milktea_startup"},
    )
    assert hits
    assert hits[0]["metadata"].get("source")


@pytest.mark.live
def test_live_fast_llm_returns_a_nonempty_response():
    _require_live_enabled()
    config = _live_config()
    assert config["FAST_LLM_API_KEY"], "FAST_LLM_API_KEY is required for live acceptance"

    llm = build_llm(
        LlmConfig(
            base_url=config["FAST_LLM_BASE_URL"],
            api_key=config["FAST_LLM_API_KEY"],
            model=config["FAST_LLM_MODEL"],
            temperature=0,
            timeout=int(config["FAST_LLM_TIMEOUT"] or 30),
            max_retries=int(config["FAST_LLM_MAX_RETRIES"] or 0),
        )
    )
    response = llm.invoke(
        [
            SystemMessage(content="Reply with one concise Chinese sentence."),
            HumanMessage(content="确认决策推演服务可用。"),
        ]
    )
    assert str(response.content).strip()
