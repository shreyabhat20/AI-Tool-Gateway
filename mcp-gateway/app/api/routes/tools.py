from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import admin_user, current_user
from app.api.schemas import PermissionRead, PermissionWrite, ToolCreate, ToolRead, ToolUpdate
from app.core.errors import GatewayError
from app.db.models import Tool, ToolPermission, User
from app.db.repositories import permission_for, tool_by_name
from app.db.session import get_db
from app.services.registry import validate_schema, validate_target_url

router = APIRouter(prefix="/tools", tags=["tools"])


def get_tool(session: Session, name: str) -> Tool:
    tool = tool_by_name(session, name)
    if tool is None:
        raise GatewayError(404, "tool_not_found", "Tool not found")
    return tool


@router.get("")
def list_tools(
    active: bool | None = None,
    risk_level: str | None = None,
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    query = select(Tool)
    if active is not None:
        query = query.where(Tool.active.is_(active))
    if risk_level:
        query = query.where(Tool.risk_level == risk_level)
    if q:
        query = query.where(Tool.name.ilike(f"%{q}%"))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    tools = session.scalars(query.order_by(Tool.id).limit(limit).offset(offset)).all()
    return {"items": [ToolRead.model_validate(tool).model_dump(mode="json") for tool in tools], "total": total, "limit": limit, "offset": offset}


@router.get("/{name}", response_model=ToolRead)
def retrieve_tool(name: str, _user: User = Depends(current_user), session: Session = Depends(get_db)) -> Tool:
    return get_tool(session, name)


@router.post("", response_model=ToolRead, status_code=201)
def create_tool(body: ToolCreate, _admin: User = Depends(admin_user), session: Session = Depends(get_db)) -> Tool:
    values = body.model_dump()
    values["input_schema"] = validate_schema(body.input_schema)
    values["target_url"] = validate_target_url(body.target_url)
    tool = Tool(**values)
    session.add(tool)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise GatewayError(409, "tool_exists", "Tool name already exists") from exc
    session.refresh(tool)
    return tool


@router.patch("/{name}", response_model=ToolRead)
def update_tool(name: str, body: ToolUpdate, _admin: User = Depends(admin_user), session: Session = Depends(get_db)) -> Tool:
    tool = get_tool(session, name)
    values = body.model_dump(exclude_unset=True)
    if "input_schema" in values:
        values["input_schema"] = validate_schema(values["input_schema"])
    if "target_url" in values:
        values["target_url"] = validate_target_url(values["target_url"])
    if any(value is None for value in values.values()):
        raise GatewayError(422, "invalid_update", "Updated fields cannot be null")
    for key, value in values.items():
        setattr(tool, key, value)
    session.commit()
    session.refresh(tool)
    return tool


@router.post("/{name}/activate", response_model=ToolRead)
def activate_tool(name: str, _admin: User = Depends(admin_user), session: Session = Depends(get_db)) -> Tool:
    tool = get_tool(session, name)
    tool.active = True
    session.commit()
    session.refresh(tool)
    return tool


@router.post("/{name}/deactivate", response_model=ToolRead)
def deactivate_tool(name: str, _admin: User = Depends(admin_user), session: Session = Depends(get_db)) -> Tool:
    tool = get_tool(session, name)
    tool.active = False
    session.commit()
    session.refresh(tool)
    return tool


@router.delete("/{name}", status_code=204)
def delete_tool(name: str, _admin: User = Depends(admin_user), session: Session = Depends(get_db)) -> Response:
    tool = get_tool(session, name)
    session.delete(tool)
    session.commit()
    return Response(status_code=204)


@router.get("/{name}/permissions", response_model=list[PermissionRead])
def list_permissions(name: str, _user: User = Depends(current_user), session: Session = Depends(get_db)) -> list[ToolPermission]:
    tool = get_tool(session, name)
    return list(session.scalars(select(ToolPermission).where(ToolPermission.tool_id == tool.id).order_by(ToolPermission.role)))


@router.put("/{name}/permissions/{role}", response_model=PermissionRead)
def set_permission(
    name: str,
    role: str,
    body: PermissionWrite,
    _admin: User = Depends(admin_user),
    session: Session = Depends(get_db),
) -> ToolPermission:
    if role != body.role or role not in {"admin", "developer", "viewer"}:
        raise GatewayError(422, "invalid_role", "Role in URL and body must match")
    if role == "admin" and not body.allowed:
        raise GatewayError(422, "invalid_permission", "Admin tool access cannot be denied")
    tool = get_tool(session, name)
    permission = permission_for(session, tool.id, role)
    if permission is None:
        permission = ToolPermission(tool_id=tool.id, role=role, allowed=body.allowed)
        session.add(permission)
    else:
        permission.allowed = body.allowed
    session.commit()
    session.refresh(permission)
    return permission

