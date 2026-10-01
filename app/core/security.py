from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import Settings
from app.core.errors import GatewayError


def issue_token(user_id: int, settings: Settings) -> str:
    if not settings.jwt_secret:
        raise GatewayError(503, "auth_unconfigured", "JWT signing key is not configured")
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.jwt_ttl_minutes)},
        settings.jwt_secret,
        algorithm="HS256",
    )


def decode_token(token: str, settings: Settings) -> int:
    if not settings.jwt_secret:
        raise GatewayError(503, "auth_unconfigured", "JWT signing key is not configured")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"require": ["sub", "exp", "iat"]})
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise GatewayError(401, "invalid_token", "Invalid or expired bearer token") from exc

