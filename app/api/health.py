"""Health Check 端点 —— 被负载均衡/监控探针调用。"""

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """返回服务健康状态。

    不查 DB/外部依赖（纯存活探针，非就绪探针）。
    就绪探针后续可加 /api/health/ready 查 DB/Chroma/LLM 连通性。
    """
    return {"status": "ok", "version": "0.1.0"}
