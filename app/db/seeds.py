from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Tool, ToolPermission, User
from app.db.session import session_factory


DEMO_TOOLS: tuple[dict[str, object], ...] = (
    {
        "name": "currency-conversion",
        "description": "Convert between fixed demo currency rates.",
        "risk_level": "low",
        "target_url": "http://currency-tool:8000/invoke",
        "input_schema": {
            "type": "object",
            "properties": {
                "amount": {"type": "number", "minimum": 0, "maximum": 1000000},
                "from_currency": {"type": "string", "enum": ["USD", "EUR", "INR"]},
                "to_currency": {"type": "string", "enum": ["USD", "EUR", "INR"]},
            },
            "required": ["amount", "from_currency", "to_currency"],
            "additionalProperties": False,
        },
    },
    {
        "name": "knowledge-search",
        "description": "Search a tiny public demo knowledge base.",
        "risk_level": "low",
        "target_url": "http://knowledge-tool:8000/invoke",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 200}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "support-ticket",
        "description": "Create a simulated support ticket without external delivery.",
        "risk_level": "medium",
        "target_url": "http://ticket-tool:8000/invoke",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 3, "maxLength": 120},
                "category": {"type": "string", "enum": ["access", "software", "hardware"]},
            },
            "required": ["summary", "category"],
            "additionalProperties": False,
        },
    },
)


def seed(session: Session) -> None:
    for username, role in (("admin", "admin"), ("developer", "developer"), ("viewer", "viewer")):
        user = session.scalar(select(User).where(User.username == username))
        if user is None:
            session.add(User(username=username, role=role, active=True))
        else:
            user.role = role
            user.active = True
    for data in DEMO_TOOLS:
        name = str(data["name"])
        tool = session.scalar(select(Tool).where(Tool.name == name))
        if tool is None:
            tool = Tool(**data, active=True)
            session.add(tool)
            session.flush()
        for role, allowed in (
            ("developer", True),
            ("viewer", name == "knowledge-search"),
        ):
            permission = session.scalar(
                select(ToolPermission).where(
                    ToolPermission.tool_id == tool.id, ToolPermission.role == role
                )
            )
            if permission is None:
                session.add(ToolPermission(tool_id=tool.id, role=role, allowed=allowed))
    session.commit()


def main() -> None:
    with session_factory()() as session:
        seed(session)


if __name__ == "__main__":
    main()

