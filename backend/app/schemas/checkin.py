"""打卡日历的响应模型。

`days` 一次给全月每一天的状态，前端不用自己算月份长度、闰年和起始星期；
日历格子的三态（已打卡 / 有任务未完成 / 没布置）也由后端直接给。
"""
from datetime import date

from pydantic import BaseModel, Field


class CheckinDayOut(BaseModel):
    date: date
    checked: bool = Field(description="当天是否已打卡")
    has_task: bool = Field(description="当天是否有任务；没有则这天本来就不用打卡")


class CalendarOut(BaseModel):
    month: str = Field(description="月份，如 2026-11")
    first_weekday: int = Field(description="当月 1 号是星期几，1=周一 … 7=周日，前端排格子用")
    days: list[CheckinDayOut]
    streak: int = Field(description="当前连续打卡天数；今天还没打卡不算断")
    longest: int = Field(description="历史最长连续天数")
    total: int = Field(description="累计打卡天数")
    checked_today: bool
    today_all_done: bool = Field(description="今天任务是否已全部完成；为真时今晚会记打卡")


class SettleOut(BaseModel):
    created: bool = Field(description="本次是否新记了一条打卡")
    checked_today: bool = Field(description="结算后今天是否已打卡")
    streak: int = Field(description="结算后的当前连续天数")
