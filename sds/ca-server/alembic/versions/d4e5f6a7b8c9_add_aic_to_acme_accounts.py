"""add nullable AIC binding to ACME accounts

Revision ID: d4e5f6a7b8c9
Revises: 9b3d2b7c1a6f
Create Date: 2026-07-10
"""

from alembic import context, op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "9b3d2b7c1a6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    column = sa.Column("aic", sa.String(length=255), nullable=True)
    if context.is_offline_mode():
        op.add_column("acme_accounts", column)
        op.create_index("ix_acme_accounts_aic", "acme_accounts", ["aic"])
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {item["name"] for item in inspector.get_columns("acme_accounts")}
    if "aic" not in columns:
        op.add_column("acme_accounts", column)

    inspector = sa.inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes("acme_accounts")}
    if "ix_acme_accounts_aic" not in indexes:
        op.create_index("ix_acme_accounts_aic", "acme_accounts", ["aic"])


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("ix_acme_accounts_aic", table_name="acme_accounts")
        op.drop_column("acme_accounts", "aic")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {item["name"] for item in inspector.get_indexes("acme_accounts")}
    if "ix_acme_accounts_aic" in indexes:
        op.drop_index("ix_acme_accounts_aic", table_name="acme_accounts")

    inspector = sa.inspect(bind)
    columns = {item["name"] for item in inspector.get_columns("acme_accounts")}
    if "aic" in columns:
        op.drop_column("acme_accounts", "aic")
