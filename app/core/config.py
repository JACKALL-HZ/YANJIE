from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Literal
from dotenv import load_dotenv

# 自动加载项目根目录 .env（无 .env 时静默降级，不影响 stub 模式）
load_dotenv()


def _env_bool(key: str, default: bool = True) -> bool:
    val = os.getenv(key, "1" if default else "0")
    return val.lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class LlmConfig:
    """单一 LLM 连接配置"""
    base_url: str
    api_key: str
    model: str
    temperature: float
    timeout: int
    max_retries: int


@dataclass(frozen=True)
class EmbeddingConfig:
    """Embedding 模型连接配置"""
    model: str
    base_url: str
    api_key: str
    timeout: int


@dataclass(frozen=True)
class Settings:
    scenario_dir: Path
    llm_use_stub: bool
    max_years: int
    max_interventions: int
    # 快模型：Agent 年度决策，80% 调用量
    fast_llm: LlmConfig
    # 慢模型：Judge 校验 + 行动计划
    slow_llm: LlmConfig
    # Embedding 模型：bge-m3 向量化
    embedding: EmbeddingConfig
    database_url: str
    # RAG 向量库持久化目录
    chroma_persist_dir: str
    # Tavily Search
    tavily_api_key: str
    # 实时网络搜索为可选增强，不应默认拖慢每轮 RAG 推演
    web_search_enabled: bool
    # MCP Server 模式开关
    mcp_enabled: bool
    mcp_transport: Literal["stdio", "http"]
    mcp_http_url: str
    mcp_http_token: str
    mcp_stdio_command: str
    mcp_timeout_seconds: float
    # RAG 独立开关：真实 LLM 模式默认启用，stub 测试默认关闭外部检索
    rag_enabled: bool
    # Judge 修订循环最大重试次数
    max_judge_revisions: int
    # LangGraph Checkpointer 连接串（开发期 SQLite，生产 PostgreSQL）
    checkpointer_url: str
    # JWT 认证
    jwt_secret: str
    access_token_expire_minutes: int


def _llm_from_env(prefix: str) -> LlmConfig:
    return LlmConfig(
        base_url=os.getenv(f"{prefix}_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.getenv(f"{prefix}_API_KEY", "ollama"),
        model=os.getenv(f"{prefix}_MODEL", "qwen2.5:14b"),
        temperature=float(os.getenv(f"{prefix}_TEMPERATURE", "0.7")),
        timeout=int(os.getenv(f"{prefix}_TIMEOUT", "30")),
        max_retries=int(os.getenv(f"{prefix}_MAX_RETRIES", "2")),
    )


def get_settings() -> Settings:
    llm_use_stub = _env_bool("LLM_USE_STUB", default=True)
    settings = Settings(
        scenario_dir=Path(os.getenv("SCENARIO_DIR", "scenarios")).resolve(),
        llm_use_stub=llm_use_stub,
        max_years=int(os.getenv("MAX_YEARS", "10")),
        max_interventions=int(os.getenv("MAX_INTERVENTIONS", "3")),
        fast_llm=_llm_from_env("FAST_LLM"),
        slow_llm=_llm_from_env("SLOW_LLM"),
        embedding=EmbeddingConfig(
            model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
            base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1"),
            api_key=os.getenv("EMBEDDING_API_KEY", ""),
            timeout=int(os.getenv("EMBEDDING_TIMEOUT", "8")),
        ),
        database_url=os.getenv("DATABASE_URL", "sqlite:///yanjie_dev.db"),
        chroma_persist_dir=os.getenv("CHROMA_PERSIST_DIR", "chroma_db"),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
        web_search_enabled=_env_bool("WEB_SEARCH_ENABLED", default=False),
        # 真实模型模式默认走本地 stdio MCP；测试/stub 模式不启用外部工具。
        mcp_enabled=_env_bool("MCP_ENABLED", default=not llm_use_stub),
        mcp_transport=os.getenv("MCP_TRANSPORT", "stdio").strip().lower(),
        mcp_http_url=os.getenv("MCP_HTTP_URL", "").strip(),
        mcp_http_token=os.getenv("MCP_HTTP_TOKEN", ""),
        mcp_stdio_command=os.getenv("MCP_STDIO_COMMAND", sys.executable).strip(),
        mcp_timeout_seconds=float(os.getenv("MCP_TIMEOUT_SECONDS", "15")),
        rag_enabled=_env_bool("RAG_ENABLED", default=not llm_use_stub),
        max_judge_revisions=int(os.getenv("MAX_JUDGE_REVISIONS", "2")),
        checkpointer_url=os.getenv("CHECKPOINTER_URL", "memory"),
        jwt_secret=os.getenv("JWT_SECRET", ""),
        access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")),
    )
    _validate_settings(settings)
    return settings


def _validate_settings(settings: Settings) -> None:
    """启动时校验 Settings 合法性，不合法抛 ValueError 阻止启动。"""
    if not settings.scenario_dir.exists():
        raise ValueError(
            f"SCENARIO_DIR does not exist: {settings.scenario_dir}"
        )
    if settings.max_years < 1 or settings.max_years > 30:
        raise ValueError(
            f"MAX_YEARS must be 1-30, got {settings.max_years}"
        )
    if settings.max_interventions < 0 or settings.max_interventions > 10:
        raise ValueError(
            f"MAX_INTERVENTIONS must be 0-10, got {settings.max_interventions}"
        )
    if settings.max_judge_revisions < 0 or settings.max_judge_revisions > 5:
        raise ValueError(
            f"MAX_JUDGE_REVISIONS must be 0-5, got {settings.max_judge_revisions}"
        )
    if settings.mcp_transport not in {"stdio", "http"}:
        raise ValueError(
            "MCP_TRANSPORT must be either 'stdio' or 'http'"
        )
    if settings.mcp_enabled and settings.mcp_transport == "http" and not settings.mcp_http_url:
        raise ValueError(
            "MCP_HTTP_URL must be configured when MCP_TRANSPORT is 'http'"
        )
    if not settings.mcp_stdio_command:
        raise ValueError("MCP_STDIO_COMMAND must not be empty")
    if not 1 <= settings.mcp_timeout_seconds <= 120:
        raise ValueError("MCP_TIMEOUT_SECONDS must be between 1 and 120")
    insecure_jwt_secrets = {
        "",
        "dev-insecure-change-me",
        "change-me",
        "replace-with-at-least-32-random-bytes",
    }
    if (
        settings.jwt_secret in insecure_jwt_secrets
        or len(settings.jwt_secret.encode("utf-8")) < 32
    ):
        raise ValueError(
            "JWT_SECRET must be configured with at least 32 random bytes"
        )
    if not 1 <= settings.access_token_expire_minutes <= 10080:
        raise ValueError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be between 1 and 10080"
        )
    if not settings.llm_use_stub:
        if not settings.fast_llm.api_key or settings.fast_llm.api_key == "ollama":
            raise ValueError(
                "LLM_USE_STUB is off but FAST_LLM_API_KEY is not configured"
            )
