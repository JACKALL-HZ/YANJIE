"""硅基流动 bge-m3 Embedding 客户端 —— AGENTS.md 固定 embedding 模型。

通过 OpenAI 兼容 API 调用，跟项目已有的 ChatOpenAI 同一套 base_url/api_key 体系。
"""

import httpx

from app.core.config import EmbeddingConfig


class SiliconFlowEmbedder:
    """bge-m3 via SiliconFlow OpenAI-compatible embeddings API。"""

    def __init__(self, config: EmbeddingConfig) -> None:
        self._base = config.base_url.rstrip("/")
        self._model = config.model
        self._timeout = config.timeout
        self._headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }

    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化，返回 [[f1,f2,...], ...] 1024 维。"""
        if not texts:
            return []
        payload = {
            "model": self._model,
            "input": texts,
            "encoding_format": "float",
        }
        try:
            resp = httpx.post(
                f"{self._base}/embeddings",
                json=payload,
                headers=self._headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in data["data"]]
        except httpx.HTTPStatusError as e:
            # 只暴露状态码，不泄露 upstream API 响应体
            raise RuntimeError(
                f"embedding API error: status={e.response.status_code}"
            ) from e

    def embed_query(self, text: str) -> list[float]:
        """单条 embed（检索查询用）。"""
        results = self.embed([text])
        return results[0]
