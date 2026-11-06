"""「今天」的唯一来源。

库里存 UTC naive，但 task_date / check_date 这类字段记的是「哪一天」，
必须按本地时区算，否则晚上 8 点之后布置的任务会落到第二天。

所有需要「今天」的地方都调这里，不要在业务代码里写 date.today()。
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings

_TZ = ZoneInfo(settings.TIMEZONE)


def local_now() -> datetime:
    """本地时区的当前时间（带时区信息，仅用于换算）。"""
    return datetime.now(_TZ)


def local_today() -> date:
    """本地时区的今天。"""
    return local_now().date()
