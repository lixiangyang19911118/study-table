"""「今天」的唯一来源。

库里存 UTC naive，但 task_date / check_date 这类字段记的是「哪一天」，
必须按本地时区算，否则晚上 8 点之后布置的任务会落到第二天。

所有需要「今天」的地方都调这里，不要在业务代码里写 date.today()。

周报最容易踩的坑也在这里：库里是 UTC，家长看的是本地周一到周日。
所以「某一周的边界」必须先按本地算出来，再换算成 UTC 去查库，
绝对不能拿 UTC 时间去取 week。
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings

_TZ = ZoneInfo(settings.TIMEZONE)


def local_now() -> datetime:
    """本地时区的当前时间（带时区信息，仅用于换算）。"""
    return datetime.now(_TZ)


def local_today() -> date:
    """本地时区的今天。"""
    return local_now().date()


def to_local(dt: datetime) -> datetime:
    """UTC naive → 本地时区 aware。库里所有 datetime 都是 UTC naive。"""
    return dt.replace(tzinfo=timezone.utc).astimezone(_TZ)


def to_utc_naive(dt: datetime) -> datetime:
    """本地 aware → UTC naive，用于和库里的时间直接比较。"""
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def local_date(dt: datetime) -> date:
    """UTC naive 时间落在本地的哪一天。"""
    return to_local(dt).date()


def day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """本地某一天 → [起, 止) 的 UTC naive 区间。"""
    start = datetime.combine(day, time.min, tzinfo=_TZ)
    end = start + timedelta(days=1)
    return to_utc_naive(start), to_utc_naive(end)


def week_bounds(day: date) -> tuple[date, date]:
    """day 所在周的周一与周日。

    ISO 8601 与中国习惯都以周一起始，口径一致，
    所以这里和 date.isocalendar() 的周号能对上。
    """
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def parse_week(text: str | None) -> tuple[date, date]:
    """'2026-W45' → (周一, 周日)。不传则取本周。"""
    if not text:
        return week_bounds(local_today())
    try:
        year_s, week_s = text.upper().split("-W")
        monday = date.fromisocalendar(int(year_s), int(week_s), 1)
    except (ValueError, AttributeError):
        raise ValueError("周号格式应为 2026-W45") from None
    return monday, monday + timedelta(days=6)

