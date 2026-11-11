"""周报响应模型。

字段分成两组，前端展示时不要混：
- `tasks.planned / completed / rate` 按 task_date 归周（这周布置的做完没有）
- `tasks.done_this_week`、`daily`、`subjects`、`spent_min` 按 reviewed_at 归周（这周实际做了多少）
"""
from pydantic import BaseModel, Field


class DayOut(BaseModel):
    date: str
    weekday: str
    done: int
    spent_min: int


class TasksPart(BaseModel):
    planned: int = Field(description="本周布置的任务数")
    completed: int = Field(description="本周布置的任务中已完成的")
    rate: float | None = Field(description="completed / planned；没布置时为 null")
    done_this_week: int = Field(description="本周实际完成数，含补做往周的")
    spent_min: int = Field(description="本周完成任务的总用时（分钟）")


class StarsPart(BaseModel):
    earned: int
    spent: int
    net: int
    balance: int = Field(description="当前余额，不是本周增量")


class SubjectOut(BaseModel):
    subject: str
    done: int


class MistakePart(BaseModel):
    added: int = Field(description="本周新增错题")
    mastered: int = Field(description="本周标记掌握")
    due: int = Field(description="当前到期未复习的错题数")


class CalcPart(BaseModel):
    rounds: int
    questions: int
    accuracy: float | None
    spent_min: int


class WeeklyOut(BaseModel):
    week: str = Field(description="如 2026-W45")
    start: str
    end: str
    tasks: TasksPart
    stars: StarsPart
    daily: list[DayOut]
    subjects: list[SubjectOut]
    mistakes: MistakePart
    calc: CalcPart
