from collections.abc import Iterator
from importlib import import_module

import fakeredis
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_cache, get_http_client
from app.core.config import get_settings
from app.db.models import Base, ToolInvocation
from app.db.seeds import seed
from app.db.session import get_db
from app.main import app


@pytest.fixture
def api(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[TestClient, Session]]:
    monkeypatch.setenv("JWT_SECRET", "test-only-signing-key-with-enough-length")
    monkeypatch.setenv("DEMO_ACCESS_KEY", "test-only-demo-key")
    get_settings.cache_clear()
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed(session)
    cache = fakeredis.FakeRedis(decode_responses=True)

    def db_override() -> Iterator[Session]:
        yield session

    def cache_override() -> Iterator[fakeredis.FakeRedis]:
        yield cache

    def response(request: httpx.Request) -> httpx.Response:
        if request.url.host == "knowledge-tool":
            return httpx.Response(200, json={"results": [{"id": "kb-2", "title": "Tool gateway"}]})
        return httpx.Response(200, json={"status": "simulated"})

    def client_override() -> Iterator[httpx.Client]:
        with httpx.Client(transport=httpx.MockTransport(response), trust_env=False) as client:
            yield client

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_cache] = cache_override
    app.dependency_overrides[get_http_client] = client_override
    monkeypatch.setattr(import_module("app.main"), "session_factory", lambda: sessionmaker(bind=engine, expire_on_commit=False))
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()
    get_settings.cache_clear()


def token(client: TestClient, username: str) -> str:
    response = client.post("/auth/demo-token", headers={"X-Demo-Key": "test-only-demo-key"}, json={"username": username})
    assert response.status_code == 200
    return str(response.json()["access_token"])


def test_invocation_permissions_and_audit(api: tuple[TestClient, Session]) -> None:
    client, session = api
    viewer = token(client, "viewer")
    headers = {"Authorization": f"Bearer {viewer}"}
    allowed = client.post("/tools/knowledge-search/invoke", headers=headers, json={"arguments": {"query": "gateway"}})
    assert allowed.status_code == 200
    assert allowed.json()["data"]["results"][0]["id"] == "kb-2"
    assert allowed.json()["request_id"] == allowed.headers["X-Request-ID"]
    assert len(allowed.json()["trace_id"]) == 32

    denied = client.post("/tools/support-ticket/invoke", headers=headers, json={"arguments": {"summary": "Need access", "category": "access"}})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"
    assert session.query(ToolInvocation).count() == 2

    admin = token(client, "admin")
    audit = client.get("/audit/invocations?actor=viewer", headers={"Authorization": f"Bearer {admin}"})
    assert audit.status_code == 200
    assert audit.json()["total"] == 2
    assert {item["outcome"] for item in audit.json()["items"]} == {"success", "permission_denied"}


def test_bad_input_never_reaches_downstream(api: tuple[TestClient, Session]) -> None:
    client, session = api
    developer = token(client, "developer")
    response = client.post("/tools/knowledge-search/invoke", headers={"Authorization": f"Bearer {developer}"}, json={"arguments": {"query": "ok", "extra": "no"}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
    audit = session.scalar(select(ToolInvocation))
    assert audit is not None and audit.outcome == "invalid_input"


def test_authentication_is_required(api: tuple[TestClient, Session]) -> None:
    client, _session = api
    response = client.get("/tools")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_unauthenticated_invocation_is_audited(api: tuple[TestClient, Session]) -> None:
    client, session = api
    response = client.post("/tools/knowledge-search/invoke", json={"arguments": {"query": "gateway"}})
    assert response.status_code == 401
    row = session.scalar(select(ToolInvocation))
    assert row is not None
    assert row.actor_name == "anonymous"
    assert row.outcome == "authentication_required"

