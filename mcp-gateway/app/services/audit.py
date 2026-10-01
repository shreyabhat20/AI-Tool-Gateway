import json
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ToolInvocation


def input_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {"keys": sorted(payload), "bytes": len(json.dumps(payload).encode("utf-8"))}


def record_invocation(
    session: Session,
    *,
    actor_id: int | None,
    actor_name: str,
    tool_id: int | None,
    tool_name: str,
    metadata: dict[str, Any],
    outcome: str,
    status_code: int,
    latency_ms: int,
    request_id: str,
    trace_id: str,
    error_code: str | None,
) -> ToolInvocation:
    event = ToolInvocation(
        actor_id=actor_id,
        actor_name=actor_name,
        tool_id=tool_id,
        tool_name=tool_name,
        input_metadata=metadata,
        outcome=outcome,
        status_code=status_code,
        latency_ms=latency_ms,
        request_id=request_id,
        trace_id=trace_id,
        error_code=error_code,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event

