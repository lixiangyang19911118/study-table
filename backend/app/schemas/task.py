"""任务的请求/响应模型。

时间字段统一序列化成带 +00:00 的 ISO 串。库里存的是 UTC naive，
直接吐给前端会被 `new Date()` 当成本地时间，晚上八点之后能差出一天。
"""
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_serializer

Subject = Literal["语文", "数学", "英语", "体育", "其他"]
Kind = Literal["normal", "redo", "calc", "dictation"]


class TaskCreate(BaseModel):
    child_id: int | None = Field(None, description="不传则落到默认孩子")
    subject: Subject = "语文"
    title: str = Field(min_length=1, max_length=128)
    kind: Kind = "normal"
    minutes_est: int = Field(20, ge=5, le=180, description="预估时长（分钟）")
    stars: int = Field(1, ge=1, le=10, description="完成后可得的星星数")
    task_date: date | None = Field(None, description="不传则算今天（本地时区）")
    note: str | None = Field(None, max_length=500, description="家长留言")
    words: list[str] | None = Field(
        None,
        description="听写词表，一行一个词。kind=dictation 时必填，"
                    "服务端会去空行、去重并限制条数与单条长度",
    )


class TaskPatch(BaseModel):
    """只有 todo 能改，且只改传了的字段。"""

    subject: Subject | None = None
    title: str | None = Field(None, min_length=1, max_length=128)
    minutes_est: int | None = Field(None, ge=5, le=180)
    stars: int | None = Field(None, ge=1, le=10)
    task_date: date | None = None
    note: str | None = Field(None, max_length=500)
    words: list[str] | None = Field(None, description="听写词表，传空数组等于清空")


class ShotIn(BaseModel):
    file_id: int = Field(description="先调 POST /files（biz_type=shot）拿到的 id")
    width: int | None = Field(None, ge=1)
    height: int | None = Field(None, ge=1)


class SubmitIn(BaseModel):
    note: str | None = Field(None, max_length=500, description="写一句说明，可与照片二选一")


class RejectIn(BaseModel):
    comment: str = Field(min_length=1, max_length=255, description="退回原因，必填")


class ApproveIn(BaseModel):
    """审核通过。错题重做的任务要顺手判一次对错，才能排下一次复习。"""

    redo_correct: bool | None = Field(
        None,
        description="仅 kind=redo 有效：true 做对了推进一轮，false 还是错回到起点。"
                    "不传则只完成任务、不动错题节奏",
    )


class ShotOut(BaseModel):
    id: int
    file_id: int
    url: str
    width: int | None = None
    height: int | None = None


class ReviewOut(BaseModel):
    id: int
    action: str
    comment: str | None = None
    created_at: datetime

    @field_serializer("created_at")
    def _utc(self, v: datetime) -> str:
        return v.replace(tzinfo=timezone.utc).isoformat()


class TaskBrief(BaseModel):
    id: int
    subject: str
    title: str
    kind: str
    minutes_est: int
    stars: int
    status: str
    source: str
    task_date: date
    spent_sec: int
    note: str | None = None
    submit_note: str | None = None
    words: list[str] | None = Field(None, description="听写词表，kind=dictation 才有")
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    shot_count: int = 0

    @field_serializer("started_at", "submitted_at", "reviewed_at")
    def _utc(self, v: datetime | None) -> str | None:
        return v.replace(tzinfo=timezone.utc).isoformat() if v else None


class MistakeRef(BaseModel):
    """错题重做任务关联的错题摘要。审核页要靠它显示原题和正确答案，
    否则家长只看到一张照片，没法判「这次做对了没有」。"""

    id: int
    subject: str
    point: str
    stem: str
    answer_own: str | None = None
    answer_right: str | None = None
    stage: int = 0
    due_date: date | None = None


class TaskDetail(TaskBrief):
    shots: list[ShotOut] = []
    reviews: list[ReviewOut] = []
    mistake: MistakeRef | None = None
