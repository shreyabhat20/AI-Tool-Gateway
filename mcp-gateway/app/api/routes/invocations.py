from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from redis import Redis
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_cache, get_http_client
from app.api.schemas import InvokeRequest
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.services.execution import invoke

router = APIRouter(prefix="/tools", tags=["invocations"])


@router.post("/{name}/invoke")
def invoke_tool(
    name: str,
    body: InvokeRequest,
    request: Request,
    actor: User = Depends(current_user),
    session: Session = Depends(get_db),
    cache: Redis = Depends(get_cache),
    client: httpx.Client = Depends(get_http_client),
) -> dict[str, Any]:
    try:
        result = invoke(
            session,
            cache,
            client,
            get_settings(),
            actor,
            name,
            body.arguments,
            request.state.request_id,
            request.state.trace_id,
        )
    finally:
        request.state.invocation_audited = True
    return {"request_id": request.state.request_id, "trace_id": request.state.trace_id, "data": result}

