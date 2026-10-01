from collections.abc import Iterator

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import GatewayError
from app.core.security import decode_token
from app.db.models import User
from app.db.repositories import user_by_id
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


def get_cache() -> Iterator[Redis]:
    cache = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        yield cache
    finally:
        cache.close()


def get_http_client() -> Iterator[httpx.Client]:
    with httpx.Client(trust_env=False) as client:
        yield client


def current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise GatewayError(401, "authentication_required", "Bearer token required")
    user_id = decode_token(credentials.credentials, get_settings())
    user = user_by_id(session, user_id)
    if user is None or not user.active:
        raise GatewayError(401, "invalid_token", "Invalid or expired bearer token")
    request.state.actor_id = user.id
    request.state.actor_name = user.username
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise GatewayError(403, "admin_required", "Administrator role required")
    return user

