from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Tool, ToolPermission, User


def user_by_id(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def user_by_name(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username == username))


def tool_by_name(session: Session, name: str) -> Tool | None:
    return session.scalar(select(Tool).where(Tool.name == name))


def permission_for(session: Session, tool_id: int, role: str) -> ToolPermission | None:
    return session.scalar(
        select(ToolPermission).where(
            ToolPermission.tool_id == tool_id,
            ToolPermission.role == role,
        )
    )

