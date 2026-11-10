"""口算的请求/响应模型。

一条硬规则：**下发出去的题目里没有答案**。
QuestionOut 只有 index / type / stem 三个字段，questions 里的 answer
永远不会出现在响应体里。判分只发生在服务端。
"""
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer

from app.schemas.task import TaskBrief


class CalcGenerateIn(BaseModel):
    child_id: int | None = Field(None, description="不传则落到默认孩子")
    count: int = Field(20, ge=5, le=50, description="每轮题数")
    range_max: int = Field(20, description="数值范围上限：10 / 20 / 100")
    types: list[str] | None = Field(None, description="题型；不传用默认六种")
    task_id: int | None = Field(None, description="挂在某个口算任务下；独立练习为空")


class QuestionOut(BaseModel):
    index: int
    type: str
    stem: str


class RoundOut(BaseModel):
    """出题结果。只含题干，不含答案。"""

    id: int
    child_id: int
    task_id: int | None = None
    status: str
    total: int
    range_max: int
    types: list[str] = []
    questions: list[QuestionOut] = []


class CalcSubmitIn(BaseModel):
    answers: list[str | None] = Field(description="逐题作答，长度与题目数一致，未答给 null")
    seconds: int | None = Field(
        None, ge=0, description="用时（秒）；不传则由服务端按出题时间推算"
    )


class WrongItemOut(BaseModel):
    index: int
    type: str
    stem: str
    your_answer: str | None = None
    right_answer: str


class CalcResultOut(BaseModel):
    """交卷结果。到这里才第一次把答案给前端——已经交过卷，看答案无害。"""

    id: int
    total: int
    right_count: int
    seconds: int
    accuracy: float
    stars_earned: int
    task: TaskBrief | None = None
    wrong: list[WrongItemOut] = []


class ToMistakesIn(BaseModel):
    indexes: list[int] | None = Field(
        None, description="要加入错题本的题号；不传表示本轮全部错题"
    )


class RoundBrief(BaseModel):
    """历史记录里的一条，不含题目明细。"""

    id: int
    created_at: datetime
    total: int
    right_count: int
    seconds: int
    range_max: int
    accuracy: float

    @field_serializer("created_at")
    def _utc(self, v: datetime) -> str:
        return v.replace(tzinfo=timezone.utc).isoformat()
