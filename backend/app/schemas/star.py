"""星星余额与流水的请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, Field


class LedgerOut(BaseModel):
    id: int
    delta: int = Field(description="正数为获得，负数为消耗")
    reason: str
    ref_type: str | None = Field(None, description="task / redemption / manual")
    created_at: datetime


class StarsOut(BaseModel):
    balance: int = Field(description="余额 = 所有流水之和")
    available: int = Field(description="可用余额 = 余额 - 待确认兑换占用的星星")
    pending: int = Field(description="待家长确认的兑换一共占了多少颗")
    ledger: list[LedgerOut]


class AdjustIn(BaseModel):
    delta: int = Field(description="正数补发，负数扣除；不能为 0", ge=-1000, le=1000)
    reason: str | None = Field(None, max_length=32, description="事由，默认「家长补发」")
