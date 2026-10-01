from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Tool, ToolInvocation, ToolPermission, User
from app.db.seeds import seed
from app.services.audit import input_metadata, record_invocation


def sqlite_session() -> Session:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine)


def test_seed_is_idempotent_and_permissions_are_distinct() -> None:
    with sqlite_session() as session:
        seed(session)
        seed(session)
        assert session.scalar(select(func.count()).select_from(User)) == 3
        assert session.scalar(select(func.count()).select_from(Tool)) == 3
        assert session.scalar(select(func.count()).select_from(ToolPermission)) == 6
        knowledge = session.scalar(select(Tool).where(Tool.name == "knowledge-search"))
        assert knowledge is not None
        viewer = session.scalar(select(ToolPermission).where(ToolPermission.tool_id == knowledge.id, ToolPermission.role == "viewer"))
        assert viewer is not None and viewer.allowed


def test_audit_stores_metadata_without_values() -> None:
    with sqlite_session() as session:
        seed(session)
        user = session.scalar(select(User).where(User.username == "developer"))
        tool = session.scalar(select(Tool).where(Tool.name == "knowledge-search"))
        assert user is not None and tool is not None
        metadata = input_metadata({"query": "private example"})
        record_invocation(
            session,
            actor_id=user.id,
            actor_name=user.username,
            tool_id=tool.id,
            tool_name=tool.name,
            metadata=metadata,
            outcome="success",
            status_code=200,
            latency_ms=12,
            request_id="test-request",
            trace_id="a" * 32,
            error_code=None,
        )
        row = session.scalar(select(ToolInvocation))
        assert row is not None
        assert row.input_metadata == {"keys": ["query"], "bytes": len('{"query": "private example"}')}
        assert "private example" not in str(row.input_metadata)

