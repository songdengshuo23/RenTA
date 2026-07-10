"""add agent supervisor review table

Revision ID: c7d8e9f0a1b2
Revises: b0f1a2c3d4e5
Create Date: 2026-05-28 11:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "b0f1a2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_supervisor_review",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("agent_acs_hash", sa.String(length=256), nullable=False),
        sa.Column("agent_acs_version", sa.Integer(), nullable=False),
        sa.Column(
            "review_mode",
            sa.String(length=64),
            nullable=False,
            server_default="registry_rules_v1",
        ),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("permission_tier", sa.String(length=16), nullable=False),
        sa.Column("scores", JSONB(), nullable=True),
        sa.Column("checks", JSONB(), nullable=True),
        sa.Column("required_fixes", JSONB(), nullable=True),
        sa.Column("passport_draft", JSONB(), nullable=True),
        sa.Column("review_result", JSONB(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="COMPLETED"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_supervisor_review_id"),
        "agent_supervisor_review",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_supervisor_review_review_id"),
        "agent_supervisor_review",
        ["review_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_agent_supervisor_review_agent_id"),
        "agent_supervisor_review",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_supervisor_review_agent_created",
        "agent_supervisor_review",
        ["agent_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_agent_supervisor_review_agent_snapshot",
        "agent_supervisor_review",
        ["agent_id", "agent_acs_hash", "agent_acs_version"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_agent_supervisor_review_agent_snapshot",
        table_name="agent_supervisor_review",
    )
    op.drop_index(
        "ix_agent_supervisor_review_agent_created",
        table_name="agent_supervisor_review",
    )
    op.drop_index(
        op.f("ix_agent_supervisor_review_agent_id"),
        table_name="agent_supervisor_review",
    )
    op.drop_index(
        op.f("ix_agent_supervisor_review_review_id"),
        table_name="agent_supervisor_review",
    )
    op.drop_index(
        op.f("ix_agent_supervisor_review_id"),
        table_name="agent_supervisor_review",
    )
    op.drop_table("agent_supervisor_review")
