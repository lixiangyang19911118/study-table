"""打卡日历。

打卡的写入点只有一个条件：当天任务**全部**变成 done。所以这个模块读多写少，
而写入必须幂等——23:55 的定时结算和孩子点开日历时的即时结算都可能碰到同一天，
两边谁先到算谁的，靠 `uk_checkin_day` 唯一键兜底。

三个口径决策：

1. **今天没打卡不算断。** 结算发生在当天结束时，孩子白天打开日历，今天必然是空格。
   这时候连续天数不能显示成 0，所以从今天往回找起点：今天没打卡就从昨天数。
2. **连续天数用「日期序列」实时算，不存字段。** 存字段就要在补记、删除、
   时区变化时同步维护，错一次就永久错；一天一条记录，扫一遍只要几百次比较。
3. **日历要同时返回「哪天有任务」。** 否则孩子只看到一片灰格，
   分不清是「我没做」还是「那天本来就没布置」，连续断了会莫名其妙。
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import local_today
from app.core.errors import BizError
from app.models import Checkin, Task


class CheckinError(BizError):
    """打卡参数不合法。"""

    def __init__(self, message: str, code: str = "invalid_checkin", status_code: int = 400):
        super().__init__(message, code, status_code)


# ---------------------------------------------------------------- 月份

def month_bounds(text: str | None) -> tuple[date, date]:
    """'2026-11' → (11-01, 11-30)。不传取本月。"""
    today = local_today()
    if not text:
        first = today.replace(day=1)
        return first, today.replace(day=monthrange(today.year, today.month)[1])
    try:
        parts = text.split("-")
        if len(parts) != 2:
            raise ValueError
        year, month = int(parts[0]), int(parts[1])
        first = date(year, month, 1)
    except (ValueError, TypeError):
        raise CheckinError("月份格式应为 2026-11") from None
    return first, first.replace(day=monthrange(first.year, first.month)[1])


# ---------------------------------------------------------------- 统计口径

def all_checked(db: Session, child_id: int) -> set[date]:
    """该孩子全部打卡日期。单孩子一年最多 365 行，全量取回比多条聚合查询更省事。"""
    return set(
        db.scalars(select(Checkin.check_date).where(Checkin.child_id == child_id))
    )


def task_dates(db: Session, child_id: int, start: date, end: date) -> set[date]:
    """区间内有任务的日期（含未完成的）。软删的不算。"""
    return set(
        db.scalars(
            select(Task.task_date).where(
                Task.child_id == child_id,
                Task.deleted_at.is_(None),
                Task.task_date >= start,
                Task.task_date <= end,
            )
        )
    )


def streak(days: set[date], today: date) -> int:
    """当前连续打卡天数。今天还没打卡则从昨天起算，不算断。"""
    cursor = today if today in days else today - timedelta(days=1)
    n = 0
    while cursor in days:
        n += 1
        cursor -= timedelta(days=1)
    return n


def longest(days: set[date]) -> int:
    """历史最长连续天数。日期排序后线性扫一遍，相邻差 1 就累加。"""
    best = cur = 0
    prev: date | None = None
    for d in sorted(days):
        cur = cur + 1 if prev is not None and (d - prev).days == 1 else 1
        best = max(best, cur)
        prev = d
    return best


def today_all_done(db: Session, child_id: int, today: date) -> bool:
    """今天是否「有任务且全部完成」——只有这种情况今晚才会记打卡。"""
    statuses = list(
        db.scalars(
            select(Task.status).where(
                Task.child_id == child_id,
                Task.task_date == today,
                Task.deleted_at.is_(None),
            )
        )
    )
    return bool(statuses) and all(s == "done" for s in statuses)


# ---------------------------------------------------------------- 结算

def settle_child(db: Session, child_id: int, day: date) -> bool:
    """当天任务全部完成则记一次打卡。返回是否新建。**不 commit**。

    jobs 里要按孩子循环，统一提交；所以这里只管「该不该加这一行」。
    """
    if not today_all_done(db, child_id, day):
        return False
    exists = db.scalar(
        select(Checkin.id).where(
            Checkin.child_id == child_id, Checkin.check_date == day
        )
    )
    if exists:
        return False
    db.add(Checkin(child_id=child_id, check_date=day))
    return True


def settle_today(db: Session, child_id: int) -> bool:
    """接口触发的即时结算。任务一全部完成就当场补记，不用等到 23:55。"""
    created = settle_child(db, child_id, local_today())
    if created:
        db.commit()
    return created


# ---------------------------------------------------------------- 日历

def calendar(db: Session, child_id: int, month: str | None) -> dict:
    """整月日历快照。前端拿到就能直接铺格子，不用自己算月份长度与起始星期。"""
    first, last = month_bounds(month)
    today = local_today()
    checked = all_checked(db, child_id)
    tasks = task_dates(db, child_id, first, last)

    days: list[dict] = []
    cursor = first
    while cursor <= last:
        days.append(
            {"date": cursor, "checked": cursor in checked, "has_task": cursor in tasks}
        )
        cursor += timedelta(days=1)

    return {
        "month": f"{first.year:04d}-{first.month:02d}",
        "first_weekday": first.isoweekday(),
        "days": days,
        "streak": streak(checked, today),
        "longest": longest(checked),
        "total": len(checked),
        "checked_today": today in checked,
        "today_all_done": today_all_done(db, child_id, today),
    }
