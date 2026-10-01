from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import admin_user
from app.api.schemas import AuditRead
from app.db.models import ToolInvocation, User
from app.db.session import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/invocations")
def list_invocations(
    actor: str | None = None,
    tool: str | None = None,
    outcome: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: User = Depends(admin_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(ToolInvocation)
    if actor:
        query = query.where(ToolInvocation.actor_name == actor)
    if tool:
        query = query.where(ToolInvocation.tool_name == tool)
    if outcome:
        query = query.where(ToolInvocation.outcome == outcome)
    if from_time:
        query = query.where(ToolInvocation.created_at >= from_time)
    if to_time:
        query = query.where(ToolInvocation.created_at <= to_time)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(query.order_by(ToolInvocation.created_at.desc(), ToolInvocation.id.desc()).limit(limit).offset(offset)).all()
    return {"items": [AuditRead.model_validate(row).model_dump(mode="json") for row in rows], "total": total, "limit": limit, "offset": offset}

