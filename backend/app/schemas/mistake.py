"""错题的请求/响应模型。

due_date 是本地日期（不带时区），原样输出 "2026-11-12"；
created_at 这类时间戳是 UTC naive，必须补 +00:00，否则前端 new Date() 会当成本地时间。
"""
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

Category = Literal["learning", "due", "mastered"]
Cause = Literal["计算错", "看错题", "概念不清", "不会做"]


class MistakeCreate(BaseModel):
    child_id: int | None = Field(None, description="不传则落到默认孩子")
    subject: str = Field("数学", max_length=16)
    point: str = Field("", max_length=128, description="知识点，如「两位数进位加法」")
    stem: str = Field("", max_length=2000, description="题干文字；与 file_id 至少有一个")
    answer_own: str | None = Field(None, max_length=500, description="孩子当时的错误答案")
    answer_right: str | None = Field(None, max_length=500, description="正确答案")
    cause: Cause | None = Field(None, description="错因，可空，事后补")
    file_id: int | None = Field(None, description="错题照片，先调 POST /files（biz_type=mistake）")


class MistakePatch(BaseModel):
    subject: str | None = Field(None, max_length=16)
    point: str | None = Field(None, max_length=128)
    stem: str | None = Field(None, max_length=2000)
    answer_own: str | None = Field(None, max_length=500)
    answer_right: str | None = Field(None, max_length=500)
    cause: Cause | None = None


class MistakeLogOut(BaseModel):
    id: int
    action: str
    is_correct: bool | None = None
    answer: str | None = None
    created_at: datetime

    @field_serializer("created_at")
    def _utc(self, v: datetime) -> str:
        return v.replace(tzinfo=timezone.utc).isoformat()


class MistakeBrief(BaseModel):
    id: int
    subject: str
    point: str
    stem: str
    answer_own: str | None = None
    answer_right: str | None = None
    cause: str | None = None
    source: str
    stage: int
    due_date: date | None = None
    mastered: bool
    file_url: str | None = None
    review_count: int = 0
    created_at: datetime

    @field_serializer("created_at")
    def _utc(self, v: datetime) -> str:
        return v.replace(tzinfo=timezone.utc).isoformat()


class MistakeDetail(MistakeBrief):
    logs: list[MistakeLogOut] = []


class MistakeCounts(BaseModel):
    learning: int
    due: int
    mastered: int
