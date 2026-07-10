"""add points wallet and transactions

Revision ID: e7f6a5b4c3d2
Revises: d9e0f1a2b3c4
Create Date: 2026-06-18 10:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f6a5b4c3d2"
down_revision: Union[str, None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "points_wallet",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("balance", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["account_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_points_wallet_id"), "points_wallet", ["id"], unique=False)
    op.create_index(op.f("ix_points_wallet_user_id"), "points_wallet", ["user_id"], unique=False)

    op.create_table(
        "points_transaction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 4), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("related_agent_aic", sa.String(length=512), nullable=True),
        sa.Column("related_agent_name", sa.String(length=255), nullable=True),
        sa.Column("counterparty_user_id", sa.Uuid(), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["counterparty_user_id"], ["account_user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["account_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_points_transaction_id"), "points_transaction", ["id"], unique=False)
    op.create_index(op.f("ix_points_transaction_user_id"), "points_transaction", ["user_id"], unique=False)
    op.create_index(op.f("ix_points_transaction_type"), "points_transaction", ["type"], unique=False)
    op.create_index(op.f("ix_points_transaction_created_at"), "points_transaction", ["created_at"], unique=False)
    op.create_index(op.f("ix_points_transaction_related_agent_aic"), "points_transaction", ["related_agent_aic"], unique=False)
    op.create_index(op.f("ix_points_transaction_counterparty_user_id"), "points_transaction", ["counterparty_user_id"], unique=False)
    op.create_index("ix_points_transaction_user_created", "points_transaction", ["user_id", "created_at"], unique=False)
    op.create_index("ix_points_transaction_reference", "points_transaction", ["reference_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_points_transaction_reference", table_name="points_transaction")
    op.drop_index("ix_points_transaction_user_created", table_name="points_transaction")
    op.drop_index(op.f("ix_points_transaction_counterparty_user_id"), table_name="points_transaction")
    op.drop_index(op.f("ix_points_transaction_related_agent_aic"), table_name="points_transaction")
    op.drop_index(op.f("ix_points_transaction_created_at"), table_name="points_transaction")
    op.drop_index(op.f("ix_points_transaction_type"), table_name="points_transaction")
    op.drop_index(op.f("ix_points_transaction_user_id"), table_name="points_transaction")
    op.drop_index(op.f("ix_points_transaction_id"), table_name="points_transaction")
    op.drop_table("points_transaction")
    op.drop_index(op.f("ix_points_wallet_user_id"), table_name="points_wallet")
    op.drop_index(op.f("ix_points_wallet_id"), table_name="points_wallet")
    op.drop_table("points_wallet")
