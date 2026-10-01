import json
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from app.core.errors import GatewayError

ALLOWED_TARGETS = {
    "currency-tool",
    "knowledge-tool",
    "ticket-tool",
}


def validate_target_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise GatewayError(422, "invalid_target", "Invalid target URL") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname not in ALLOWED_TARGETS
        or port != 8000
        or parsed.path != "/invoke"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.netloc != f"{parsed.hostname}:8000"
    ):
        raise GatewayError(422, "invalid_target", "Target must be a local demo tool /invoke URL")
    return value


def validate_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if len(json.dumps(schema)) > 10_000 or schema.get("type") != "object":
        raise GatewayError(422, "invalid_schema", "A small object JSON schema is required")
    def has_remote_reference(value: object) -> bool:
        if isinstance(value, dict):
            return any(key in {"$ref", "$dynamicRef"} or has_remote_reference(item) for key, item in value.items())
        if isinstance(value, list):
            return any(has_remote_reference(item) for item in value)
        return False

    if has_remote_reference(schema):
        raise GatewayError(422, "invalid_schema", "Schema references are not allowed")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise GatewayError(422, "invalid_schema", "Invalid JSON input schema") from exc
    return schema

