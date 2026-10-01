import logging
import time
from typing import Any

import httpx
from jsonschema import Draft202012Validator
from opentelemetry import trace
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import GatewayError
from app.core.metrics import AUTH_DENIALS, CIRCUIT_OPEN, DOWNSTREAM_ERRORS, RATE_LIMITS, TOOL_INVOCATIONS
from app.db.models import Tool, User
from app.db.repositories import tool_by_name
from app.services.audit import input_metadata, record_invocation
from app.services.authorization import can_invoke, require_permission
from app.services.rate_limits import RateLimiter

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def validate_input(schema: dict[str, Any], payload: dict[str, Any]) -> None:
    errors = list(Draft202012Validator(schema).iter_errors(payload))
    if errors:
        raise GatewayError(422, "invalid_input", "Input does not match the tool schema")


class CircuitBreaker:
    def __init__(self, cache: Redis, threshold: int, cooldown_seconds: int) -> None:
        self.cache = cache
        self.threshold = threshold
        self.cooldown_seconds = cooldown_seconds

    def before_call(self, tool_id: int) -> None:
        try:
            if self.cache.exists(f"circuit:open:{tool_id}"):
                raise GatewayError(503, "circuit_open", "Tool temporarily unavailable")
        except RedisError as exc:
            raise GatewayError(503, "circuit_unavailable", "Circuit state unavailable") from exc

    def failure(self, tool_id: int) -> None:
        try:
            with self.cache.pipeline(transaction=True) as pipe:
                pipe.incr(f"circuit:failures:{tool_id}")
                pipe.expire(f"circuit:failures:{tool_id}", self.cooldown_seconds)
                count = int(pipe.execute()[0])
            if count >= self.threshold:
                self.cache.set(f"circuit:open:{tool_id}", "1", ex=self.cooldown_seconds)
                CIRCUIT_OPEN.labels(tool=str(tool_id)).set(1)
        except RedisError as exc:
            raise GatewayError(503, "circuit_unavailable", "Circuit state unavailable") from exc

    def success(self, tool_id: int) -> None:
        try:
            self.cache.delete(f"circuit:failures:{tool_id}", f"circuit:open:{tool_id}")
            CIRCUIT_OPEN.labels(tool=str(tool_id)).set(0)
        except RedisError as exc:
            raise GatewayError(503, "circuit_unavailable", "Circuit state unavailable") from exc


def call_downstream(client: httpx.Client, tool: Tool, payload: dict[str, Any], request_id: str, timeout: float) -> dict[str, Any]:
    for attempt in range(2):
        try:
            response = client.post(tool.target_url, json=payload, headers={"X-Request-ID": request_id}, timeout=timeout)
        except httpx.TransportError as exc:
            if attempt == 0:
                continue
            code = "downstream_timeout" if isinstance(exc, httpx.TimeoutException) else "downstream_unavailable"
            raise GatewayError(504 if code == "downstream_timeout" else 502, code, "Demo tool unavailable") from exc
        if response.status_code in {502, 503, 504} and attempt == 0:
            continue
        if response.status_code >= 400:
            raise GatewayError(502, "downstream_rejected", "Demo tool rejected the request")
        try:
            data = response.json()
        except ValueError as exc:
            raise GatewayError(502, "downstream_invalid_response", "Demo tool returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise GatewayError(502, "downstream_invalid_response", "Demo tool returned invalid data")
        return data
    raise GatewayError(502, "downstream_unavailable", "Demo tool unavailable")


def invoke(
    session: Session,
    cache: Redis,
    client: httpx.Client,
    settings: Settings,
    actor: User,
    tool_name: str,
    payload: dict[str, Any],
    request_id: str,
    trace_id: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    tool: Tool | None = None
    error: GatewayError | None = None
    result: dict[str, Any] | None = None
    with tracer.start_as_current_span("tool.invoke") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("actor.role", actor.role)
        span.set_attribute("request.id", request_id)
        try:
            tool = tool_by_name(session, tool_name)
            if tool is None:
                raise GatewayError(404, "tool_not_found", "Tool not found")
            if not tool.active:
                raise GatewayError(409, "tool_inactive", "Tool is inactive")
            require_permission(actor.role, can_invoke(session, tool.id, actor.role))
            validate_input(tool.input_schema, payload)
            RateLimiter(cache, settings.rate_limit_per_minute).check(actor.id, tool.id)
            breaker = CircuitBreaker(cache, settings.circuit_failure_threshold, settings.circuit_cooldown_seconds)
            breaker.before_call(tool.id)
            try:
                result = call_downstream(client, tool, payload, request_id, settings.downstream_timeout_seconds)
            except GatewayError as exc:
                if exc.code in {"downstream_timeout", "downstream_unavailable", "downstream_error"}:
                    breaker.failure(tool.id)
                raise
            breaker.success(tool.id)
        except GatewayError as exc:
            error = exc
            if exc.code == "permission_denied":
                AUTH_DENIALS.labels(tool=tool_name).inc()
            elif exc.code == "rate_limited":
                RATE_LIMITS.labels(tool=tool_name).inc()
            elif exc.code.startswith("downstream_"):
                DOWNSTREAM_ERRORS.labels(tool=tool_name).inc()
            span.set_attribute("error.code", exc.code)
        except Exception:
            logger.exception("unexpected invocation error")
            session.rollback()
            error = GatewayError(500, "internal_error", "Tool invocation failed")
            span.set_attribute("error.code", error.code)
        finally:
            outcome = "success" if error is None else error.code
            TOOL_INVOCATIONS.labels(tool=tool_name, outcome=outcome).inc()
            latency_ms = max(0, int((time.perf_counter() - started) * 1000))
            record_invocation(
                session,
                actor_id=actor.id,
                actor_name=actor.username,
                tool_id=tool.id if tool else None,
                tool_name=tool_name,
                metadata=input_metadata(payload),
                outcome=outcome,
                status_code=200 if error is None else error.status_code,
                latency_ms=latency_ms,
                request_id=request_id,
                trace_id=trace_id,
                error_code=None if error is None else error.code,
            )
            logger.info("tool invocation", extra={"request_id": request_id, "trace_id": trace_id, "actor": actor.username, "tool": tool_name, "outcome": outcome})
    if error is not None:
        raise error
    assert result is not None
    return result

