"""奖励与兑换的请求/响应模型。"""
from datetime import datetime

from pydantic import BaseModel, Field


class RewardIn(BaseModel):
    name: str = Field(min_length=1, max_length=64, description="如「看动画片 20 分钟」")
    cost: int = Field(ge=1, le=999, description="兑换所需星星数")


class RewardPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    cost: int | None = Field(None, ge=1, le=999)
    status: str | None = Field(None, pattern="^(on|off)$", description="on 可兑换 / off 下架")


class RewardOut(BaseModel):
    id: int
    name: str
    cost: int
    status: str
    affordable: bool = Field(
        False, description="按当前可用余额够不够换；前端不必自己算"
    )


class RedeemIn(BaseModel):
    note: str | None = Field(None, max_length=255, description="孩子附言，可不填")


class DecideIn(BaseModel):
    note: str | None = Field(None, max_length=255, description="家长留言；拒绝时必填")


class RedemptionOut(BaseModel):
    id: int
    reward_id: int | None
    reward_name: str = Field(description="申请时的名称快照，奖励改名后仍是当时的名字")
    cost: int = Field(description="申请时的价格快照")
    status: str = Field(description="pending / approved / rejected / cancelled")
    note: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
