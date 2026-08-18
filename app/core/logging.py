"""结构化日志配置。

基于 Python logging + RichHandler，提供统一的 logger 获取方式。
所有模块通过 `get_logger(__name__)` 获取 logger，替代 `print()` 和裸 `logging.getLogger()`。

环境变量:
    LOG_LEVEL: 日志级别（dev=DEBUG / prod=INFO），默认 INFO
    PYANJIE_ENV: 环境标识，production 时关闭 rich_tracebacks（防堆栈泄露）

用法：
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("推演已启动", extra={"session_id": sid, "scenario_id": scid})
"""

import logging
import os
from typing import Any


def setup_logging(level: int = logging.INFO) -> None:
    """在应用启动时调用一次，配置根 logger 和项目日志级别。

    参数 level 按环境覆盖日志级别（dev=DEBUG / prod=INFO）。
    """
    root = logging.getLogger()
    # 避免重复添加 handler（uvicorn reload 场景）
    if root.handlers:
        return

    is_production = os.getenv("PYANJIE_ENV", "").lower() == "production"

    # 尝试 RichHandler（可选依赖，未安装时降级 stream handler）
    try:
        from rich.logging import RichHandler

        handler: logging.Handler = RichHandler(
            rich_tracebacks=not is_production,  # 生产环境关闭 rich tracebacks
            show_time=True,
            show_path=not is_production,        # 生产环境隐藏文件路径
        )
    except ImportError:
        handler = logging.StreamHandler()
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)

    root.handlers = [handler]
    root.setLevel(level)

    # 项目日志级别
    logging.getLogger("app").setLevel(level)

    # 第三方库降噪
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str, **extra: Any) -> logging.LoggerAdapter:
    """获取带结构化上下文的 logger 适配器。

    等价于 `logging.getLogger(name)`，但支持 extra 字段注入。
    """
    base = logging.getLogger(name)
    if extra:
        return logging.LoggerAdapter(base, extra)
    return base  # type: ignore[return-value]
