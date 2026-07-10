from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

import uuid6
from pydantic import ConfigDict
from sqlalchemy import Column, Index, Numeric, String, Text, TIMESTAMP
from sqlmodel import Field, SQLModel

from app.utils.utils import get_beijing_time


class PointsWallet(SQLModel, table=True):
    __tablename__ = "points_wallet"

    id: uuid.UUID = Field(default_factory=uuid6.uuid7, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="account_user.id", unique=True, index=True)
    balance: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(18, 4), nullable=False, server_default="0"),
    )
    created_at: datetime = Field(
        default_factory=get_beijing_time,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_beijing_time,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False),
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PointsTransaction(SQLModel, table=True):
    __tablename__ = "points_transaction"
    __table_args__ = (
        Index("ix_points_transaction_user_created", "user_id", "created_at"),
        Index("ix_points_transaction_reference", "reference_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid6.uuid7, primary_key=True, index=True)
    user_id: uuid.UUID = Field(foreign_key="account_user.id", index=True)
    type: str = Field(sa_column=Column(String(32), nullable=False, index=True))
    amount: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))
    balance_after: Decimal = Field(sa_column=Column(Numeric(18, 4), nullable=False))
    description: str = Field(default="", sa_column=Column(String(255), nullable=False, server_default=""))
    memo: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    related_agent_aic: Optional[str] = Field(default=None, sa_column=Column(String(512), nullable=True, index=True))
    related_agent_name: Optional[str] = Field(default=None, sa_column=Column(String(255), nullable=True))
    counterparty_user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="account_user.id", index=True)
    reference_id: Optional[str] = Field(default=None, sa_column=Column(String(128), nullable=True))
    created_at: datetime = Field(
        default_factory=get_beijing_time,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False, index=True),
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)
