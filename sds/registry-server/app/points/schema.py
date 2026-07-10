from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, Field


class AmountRequest(BaseModel):
    amount: float = Field(gt=0)


class AgentCallSettleRequest(BaseModel):
    requester_user_id: uuid.UUID
    agent_aic: str
    agent_name: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    execution_id: Optional[str] = None
    run_id: Optional[str] = None
    task_id: Optional[str] = None
    reference_id: Optional[str] = None


class PointsSummaryResponse(BaseModel):
    balance: float
    cumulative_income: float
    cumulative_expense: float


class PointsTransactionResponse(BaseModel):
    id: uuid.UUID
    type: str
    amount: float
    balance_after: float
    description: str
    memo: Optional[str] = None
    related_agent_aic: Optional[str] = None
    related_agent_name: Optional[str] = None
    counterparty_user_id: Optional[uuid.UUID] = None
    reference_id: Optional[str] = None
    created_at: datetime


class PointsTransactionListResponse(BaseModel):
    items: List[PointsTransactionResponse]
    total: int
    page_num: int
    page_size: int


class PointsTrendItem(BaseModel):
    date: str
    income: float
    expense: float


class AgentCallSettleResponse(BaseModel):
    settled: bool
    skipped: bool = False
    reason: str = ""
    amount: float = 0
    requester_user_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    consume_transaction_id: Optional[uuid.UUID] = None
    income_transaction_id: Optional[uuid.UUID] = None

