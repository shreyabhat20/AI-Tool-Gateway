from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Role = Literal["admin", "developer", "viewer"]
Risk = Literal["low", "medium", "high"]


class DemoTokenRequest(BaseModel):
    username: str


class ToolCreate(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{2,79}$")
    description: str = Field(min_length=1, max_length=1000)
    input_schema: dict[str, Any]
    risk_level: Risk
    active: bool = True
    target_url: str


class ToolUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=1000)
    input_schema: dict[str, Any] | None = None
    risk_level: Risk | None = None
    active: bool | None = None
    target_url: str | None = None


class ToolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    input_schema: dict[str, Any]
    risk_level: Risk
    active: bool
    target_url: str
    created_at: datetime
    updated_at: datetime


class PermissionWrite(BaseModel):
    role: Role
    allowed: bool


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool_id: int
    role: Role
    allowed: bool


class InvokeRequest(BaseModel):
    arguments: dict[str, Any]


class AuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_name: str
    tool_name: str
    input_metadata: dict[str, Any]
    outcome: str
    status_code: int
    latency_ms: int
    request_id: str
    trace_id: str
    error_code: str | None
    created_at: datetime

