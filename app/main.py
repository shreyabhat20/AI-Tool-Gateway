import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from prometheus_client import make_asgi_app
from redis import Redis
from sqlalchemy import text

from app.api.routes import audit, auth, invocations, tools
from app.core.config import get_settings
from app.core.errors import GatewayError
from app.core.logging import configure_logging
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS, TOOL_INVOCATIONS
from app.core.tracing import configure_tracing
from app.db.session import session_factory
from app.services.audit import record_invocation

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
INVOKE_PATH = re.compile(r"^/tools/([a-z][a-z0-9-]*)/invoke$")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing()
    HTTPXClientInstrumentor().instrument()
    yield
    HTTPXClientInstrumentor().uninstrument()


app = FastAPI(title="MCP Tool Gateway", version="0.2.0", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(tools.router)
app.include_router(invocations.router)
app.include_router(audit.router)
app.mount("/metrics", make_asgi_app())
FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    request.state.request_id = str(uuid4())
    with tracer.start_as_current_span("gateway.http") as span:
        request.state.trace_id = f"{span.get_span_context().trace_id:032x}"
        span.set_attribute("http.method", request.method)
        span.set_attribute("request.id", request.state.request_id)
        started = time.perf_counter()
        response = await call_next(request)
        match = INVOKE_PATH.fullmatch(request.url.path) if request.method == "POST" else None
        if match and not getattr(request.state, "invocation_audited", False):
            outcome = "authentication_required" if response.status_code == 401 else "request_rejected"
            if response.status_code == 422:
                outcome = "request_validation_error"
            with session_factory()() as session:
                record_invocation(
                    session,
                    actor_id=getattr(request.state, "actor_id", None),
                    actor_name=getattr(request.state, "actor_name", "anonymous"),
                    tool_id=None,
                    tool_name=match.group(1),
                    metadata={"keys": [], "bytes": 0},
                    outcome=outcome,
                    status_code=response.status_code,
                    latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
                    request_id=request.state.request_id,
                    trace_id=request.state.trace_id,
                    error_code=outcome,
                )
            TOOL_INVOCATIONS.labels(tool=match.group(1), outcome=outcome).inc()
        route = request.scope.get("route")
        route_name = getattr(route, "path", "unmatched")
        span.set_attribute("http.route", route_name)
        duration = time.perf_counter() - started
        HTTP_REQUESTS.labels(method=request.method, route=route_name, status=str(response.status_code)).inc()
        HTTP_LATENCY.labels(method=request.method, route=route_name).observe(duration)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Trace-ID"] = request.state.trace_id
        logger.info("http request", extra={"request_id": request.state.request_id, "trace_id": request.state.trace_id, "outcome": str(response.status_code)})
        return response


@app.exception_handler(GatewayError)
async def gateway_error(request: Request, error: GatewayError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": {"code": error.code, "message": error.message}, "request_id": request.state.request_id, "trace_id": request.state.trace_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, _error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "request_validation_error", "message": "Invalid request"}, "request_id": request.state.request_id, "trace_id": request.state.trace_id},
    )


@app.get("/health/live", tags=["health"])
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def ready() -> dict[str, str]:
    settings = get_settings()
    if not settings.jwt_secret or not settings.demo_access_key:
        raise GatewayError(503, "configuration_unavailable", "Local auth keys are not configured")
    try:
        with session_factory()() as session:
            session.execute(text("SELECT 1"))
        with Redis.from_url(settings.redis_url) as cache:
            cache.ping()
    except Exception as exc:
        raise GatewayError(503, "dependencies_unavailable", "Database or Redis unavailable") from exc
    return {"status": "ready"}

