"""add EAB credential table

Revision ID: f1a2b3c4d5e6
Revises: e7f6a5b4c3d2
Create Date: 2026-07-10 11:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e7f6a5b4c3d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eab_credential",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("key_id", sa.String(), nullable=False),
        sa.Column("mac_key_encrypted", sa.String(), nullable=False),
        sa.Column("aic", sa.String(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "is_consumed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("consumed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["account_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_eab_credential_id"), "eab_credential", ["id"])
    op.create_index(
        op.f("ix_eab_credential_key_id"),
        "eab_credential",
        ["key_id"],
        unique=True,
    )
    op.create_index(op.f("ix_eab_credential_aic"), "eab_credential", ["aic"])
    op.create_index(
        op.f("ix_eab_credential_user_id"), "eab_credential", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_eab_credential_user_id"), table_name="eab_credential")
    op.drop_index(op.f("ix_eab_credential_aic"), table_name="eab_credential")
    op.drop_index(op.f("ix_eab_credential_key_id"), table_name="eab_credential")
    op.drop_index(op.f("ix_eab_credential_id"), table_name="eab_credential")
    op.drop_table("eab_credential")
