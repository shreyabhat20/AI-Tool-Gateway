import hmac

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.schemas import DemoTokenRequest
from app.core.config import get_settings
from app.core.errors import GatewayError
from app.core.security import issue_token
from app.db.repositories import user_by_name
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/demo-token")
def demo_token(
    body: DemoTokenRequest,
    x_demo_key: str | None = Header(default=None),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    if not settings.demo_access_key or not x_demo_key or not hmac.compare_digest(x_demo_key, settings.demo_access_key):
        raise GatewayError(401, "invalid_demo_key", "Invalid demo access key")
    user = user_by_name(session, body.username)
    if user is None or not user.active:
        raise GatewayError(404, "demo_user_not_found", "Demo user not found")
    return {"access_token": issue_token(user.id, settings), "token_type": "bearer"}

