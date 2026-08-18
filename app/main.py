from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.ask import router as ask_router
from app.api.auth import router as auth_router
from app.api.assistant import router as assistant_router
from app.api.diary import router as diary_router
from app.api.health import router as health_router
from app.api.profiles import router as profiles_router
from app.api.report import router as report_router
from app.api.scenarios import router as scenarios_router
from app.api.sessions import router as sessions_router
from app.api.simulation import router as simulation_router
from app.api.stream import router as stream_router
from app.core.errors import (
    InvalidScenarioIdError,
    ScenarioIdMismatchError,
    ScenarioNotFoundError,
)
from app.core.logging import get_logger, setup_logging
from app.middleware.auth import ApiKeyMiddleware
from app.middleware.body_limit import BodyLimitMiddleware
from app.middleware.cors import build_cors_middleware
from app.middleware.gzip import build_gzip_middleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="YanJie AI", version="0.1.0")

# ── 中间件栈（注册顺序 = 执行顺序） ──────────────────────────
app.add_middleware(RequestIdMiddleware)
app.add_middleware(ApiKeyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(BodyLimitMiddleware)

cors_cls, cors_kwargs = build_cors_middleware()
app.add_middleware(cors_cls, **cors_kwargs)

gzip_cls, gzip_kwargs = build_gzip_middleware()
app.add_middleware(gzip_cls, **gzip_kwargs)

app.add_middleware(SecurityHeadersMiddleware)

# ── 路由注册 ──────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(ask_router)
app.include_router(assistant_router)
app.include_router(diary_router)
app.include_router(profiles_router)
app.include_router(report_router)
app.include_router(simulation_router)
app.include_router(stream_router)
app.include_router(scenarios_router)
app.include_router(sessions_router)
app.include_router(auth_router)


# ── 异常处理 ──────────────────────────────────────────────────

def _get_request_id(request: Request) -> str:
    """从请求状态获取 X-Request-ID（由 RequestIdMiddleware 注入）。"""
    return str(getattr(request.state, "request_id", str(uuid4())))


def _error_response(
    code: str,
    message: str,
    status_code: int,
    request_id: str = "",
    detail: dict | None = None,
) -> JSONResponse:
    body: dict = {"code": code, "message": message, "request_id": request_id}
    if detail:
        body["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException,
) -> JSONResponse:
    """将 HTTPException(detail={code,message}) 转成统一错误格式。"""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": detail["code"],
                "message": detail.get("message", ""),
                "request_id": _get_request_id(request),
            },
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": str(detail),
            "request_id": _get_request_id(request),
        },
    )


@app.exception_handler(ScenarioNotFoundError)
async def scenario_not_found_handler(
    request: Request, exc: ScenarioNotFoundError,
) -> JSONResponse:
    return _error_response(
        "SCENARIO_NOT_FOUND", "scenario not found", 404,
        request_id=_get_request_id(request),
        detail={"scenario_id": exc.scenario_id},
    )


@app.exception_handler(InvalidScenarioIdError)
async def invalid_scenario_id_handler(
    request: Request, exc: InvalidScenarioIdError,
) -> JSONResponse:
    return _error_response(
        "INVALID_SCENARIO_ID", "invalid scenario id", 422,
        request_id=_get_request_id(request),
        detail={"scenario_id": str(exc.scenario_id)},
    )


@app.exception_handler(ScenarioIdMismatchError)
async def scenario_id_mismatch_handler(
    request: Request, exc: ScenarioIdMismatchError,
) -> JSONResponse:
    return _error_response(
        "SCENARIO_ID_MISMATCH", "scenario id mismatch", 422,
        request_id=_get_request_id(request),
        detail={"expected": exc.expected, "actual": exc.actual},
    )


def _sanitize_errors(errors: list[dict]) -> list[dict]:
    """清洗 Pydantic 验证错误，去掉内部实现细节（ctx/url/input）。"""
    sanitized = []
    for e in errors:
        sanitized.append({
            "loc": e.get("loc", []),
            "msg": e.get("msg", ""),
            "type": e.get("type", ""),
        })
    return sanitized


@app.exception_handler(RequestValidationError)
async def request_validation_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    return _error_response(
        "INVALID_REQUEST", "request validation failed", 422,
        request_id=_get_request_id(request),
        detail={"errors": _sanitize_errors(exc.errors())},
    )


@app.exception_handler(ValueError)
async def value_error_handler(
    request: Request, exc: ValueError,
) -> JSONResponse:
    logger.warning("simulation value error: %s", exc)
    return _error_response(
        "INVALID_REQUEST", "invalid simulation input", 422,
        request_id=_get_request_id(request),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request, exc: Exception,
) -> JSONResponse:
    logger.exception("unhandled exception on %s %s", request.method, request.url)
    return _error_response(
        "INTERNAL_ERROR", "internal server error", 500,
        request_id=_get_request_id(request),
    )
