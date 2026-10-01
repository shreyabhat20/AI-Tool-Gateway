import httpx
import pytest

from app.core.errors import GatewayError
from app.db.models import Tool
from app.services.execution import call_downstream
from app.services.registry import validate_schema, validate_target_url


def test_registry_rejects_non_demo_targets_and_remote_references() -> None:
    assert validate_target_url("http://knowledge-tool:8000/invoke") == "http://knowledge-tool:8000/invoke"
    for target in ("http://127.0.0.1:8000/invoke", "http://knowledge-tool:8000/other", "http://knowledge-tool:bad/invoke"):
        with pytest.raises(GatewayError) as error:
            validate_target_url(target)
        assert error.value.code == "invalid_target"
    with pytest.raises(GatewayError) as error:
        validate_schema({"type": "object", "properties": {"x": {"$ref": "https://example.com/schema"}}})
    assert error.value.code == "invalid_schema"


def test_retry_only_on_transient_failure() -> None:
    calls = 0

    def transient(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503 if calls == 1 else 200, json={"ok": True})

    tool = Tool(name="knowledge-search", description="demo", input_schema={"type": "object"}, risk_level="low", active=True, target_url="http://knowledge-tool:8000/invoke")
    with httpx.Client(transport=httpx.MockTransport(transient), trust_env=False) as client:
        assert call_downstream(client, tool, {}, "request-id", 1.0) == {"ok": True}
    assert calls == 2

    calls = 0

    def rejected(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, json={"error": "bad input"})

    with httpx.Client(transport=httpx.MockTransport(rejected), trust_env=False) as client:
        with pytest.raises(GatewayError) as error:
            call_downstream(client, tool, {}, "request-id", 1.0)
    assert error.value.code == "downstream_rejected"
    assert calls == 1

