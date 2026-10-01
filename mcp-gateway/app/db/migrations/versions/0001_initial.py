"""Initial registry, identity, permission, and invocation tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'developer', 'viewer')", name="ck_users_role"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("input_schema", JSONB(), nullable=False),
        sa.Column("risk_level", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("target_url", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high')", name="ck_tools_risk"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_tools_name", "tools", ["name"])
    op.create_index("ix_tools_active_risk", "tools", ["active", "risk_level"])
    op.create_table(
        "tool_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'developer', 'viewer')", name="ck_permissions_role"),
        sa.UniqueConstraint("tool_id", "role", name="uq_permission_tool_role"),
    )
    op.create_index("ix_tool_permissions_tool_id", "tool_permissions", ["tool_id"])
    op.create_table(
        "tool_invocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_name", sa.String(80), nullable=False),
        sa.Column("tool_id", sa.Integer(), sa.ForeignKey("tools.id", ondelete="SET NULL")),
        sa.Column("tool_name", sa.String(80), nullable=False),
        sa.Column("input_metadata", JSONB(), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("trace_id", sa.String(32), nullable=False),
        sa.Column("error_code", sa.String(60)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_invocations_trace_id", "tool_invocations", ["trace_id"])
    op.create_index("ix_tool_invocations_created_at", "tool_invocations", ["created_at"])
    op.create_index("ix_invocations_actor_time", "tool_invocations", ["actor_id", "created_at"])
    op.create_index("ix_invocations_tool_time", "tool_invocations", ["tool_id", "created_at"])
    op.create_index("ix_invocations_outcome_time", "tool_invocations", ["outcome", "created_at"])


def downgrade() -> None:
    op.drop_table("tool_invocations")
    op.drop_table("tool_permissions")
    op.drop_table("tools")
    op.drop_table("users")

