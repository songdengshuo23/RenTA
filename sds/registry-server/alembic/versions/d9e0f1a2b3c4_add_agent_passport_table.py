"""add agent passport table

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b2
Create Date: 2026-05-28 12:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_passport",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("passport_id", sa.String(length=128), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("passport_version", sa.String(length=32), nullable=False, server_default="1.0"),
        sa.Column("acs_hash", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("acs_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("permission_tier", sa.String(length=16), nullable=False),
        sa.Column("passport_payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("review_after", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agent.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_passport_id"), "agent_passport", ["id"], unique=False)
    op.create_index(
        op.f("ix_agent_passport_passport_id"),
        "agent_passport",
        ["passport_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_agent_passport_agent_id"),
        "agent_passport",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_passport_review_id"),
        "agent_passport",
        ["review_id"],
        unique=False,
    )
    op.create_index(
        "ix_agent_passport_agent_created",
        "agent_passport",
        ["agent_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_agent_passport_review",
        "agent_passport",
        ["review_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_agent_passport_review", table_name="agent_passport")
    op.drop_index("ix_agent_passport_agent_created", table_name="agent_passport")
    op.drop_index(op.f("ix_agent_passport_review_id"), table_name="agent_passport")
    op.drop_index(op.f("ix_agent_passport_agent_id"), table_name="agent_passport")
    op.drop_index(op.f("ix_agent_passport_passport_id"), table_name="agent_passport")
    op.drop_index(op.f("ix_agent_passport_id"), table_name="agent_passport")
    op.drop_table("agent_passport")
