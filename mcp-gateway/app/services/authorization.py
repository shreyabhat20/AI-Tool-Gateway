from sqlalchemy.orm import Session

from app.core.errors import GatewayError
from app.db.repositories import permission_for


def require_permission(role: str, allowed: bool) -> None:
    if role != "admin" and not allowed:
        raise GatewayError(403, "permission_denied", "Your role cannot invoke this tool")


def can_invoke(session: Session, tool_id: int, role: str) -> bool:
    if role == "admin":
        return True
    permission = permission_for(session, tool_id, role)
    return bool(permission and permission.allowed)

