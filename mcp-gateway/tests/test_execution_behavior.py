import fakeredis
import pytest

from app.core.errors import GatewayError
from app.services.execution import CircuitBreaker, validate_input
from app.services.rate_limits import RateLimiter


SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"query": {"type": "string", "minLength": 1}},
    "required": ["query"],
    "additionalProperties": False,
}


def test_schema_rejects_extra_arguments() -> None:
    validate_input(SCHEMA, {"query": "hello"})
    with pytest.raises(GatewayError) as error:
        validate_input(SCHEMA, {"query": "hello", "secret": "no"})
    assert error.value.code == "invalid_input"


def test_rate_limit_is_scoped_to_actor_and_tool() -> None:
    cache = fakeredis.FakeRedis(decode_responses=True)
    limiter = RateLimiter(cache, limit=2, window_seconds=60)
    limiter.check(1, 1)
    limiter.check(1, 1)
    with pytest.raises(GatewayError) as error:
        limiter.check(1, 1)
    assert error.value.status_code == 429
    limiter.check(2, 1)
    limiter.check(1, 2)


def test_circuit_opens_after_transient_failures_and_recovers() -> None:
    cache = fakeredis.FakeRedis(decode_responses=True)
    breaker = CircuitBreaker(cache, threshold=2, cooldown_seconds=30)
    breaker.before_call(1)
    breaker.failure(1)
    breaker.failure(1)
    with pytest.raises(GatewayError) as error:
        breaker.before_call(1)
    assert error.value.code == "circuit_open"
    breaker.success(1)
    breaker.before_call(1)

