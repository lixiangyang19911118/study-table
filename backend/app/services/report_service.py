"""周报：实时聚合，不读快照。

为什么不建周报表：快照和流水一旦对不上，家长会先怀疑数字，再怀疑产品。
星星是纯流水、任务是状态机，两者都能随时重算出任意一周，
存一份快照只会多一个需要同步的真相来源。

**口径里唯一需要解释清楚的地方**：一周有两组数字。

- `planned` / `completed` / `rate` 按 `task_date` 归周 —— 回答「这周布置的做完了吗」
- `done_this_week` / 每日分布 / 科目分布 / 用时 按 `reviewed_at` 归周 —— 回答「这周实际干了多少」

周日补做上周的题，会算进第二组、不算进第一组。这不是 bug：
对家长来说「布置了 10 条只做完 8 条」和「这周共完成 11 条」都是真的，
但不能相除得到 110% 的完成率。
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import (
    day_bounds_utc, local_date, local_today, parse_week,
)
from app.models import CalcRecord, Mistake, MistakeLog, StarLedger, Task
from app.services import star_service

WEEKDAY_CN = ("一", "二", "三", "四", "五", "六", "日")


def weekly(db: Session, child_id: int, week_text: str | None = None) -> dict:
    monday, sunday = parse_week(week_text)
    start_utc, _ = day_bounds_utc(monday)
    _, end_utc = day_bounds_utc(sunday)

    # ---- 第一组：按 task_date 归周，看「这周布置的」完成情况
    planned_total, planned_done = _planned_stats(db, child_id, monday, sunday)

    # ---- 第二组：按 reviewed_at 归周，看「这周实际做了多少」
    finished = list(
        db.scalars(
            select(Task).where(
                Task.child_id == child_id,
                Task.status == "done",
                Task.deleted_at.is_(None),
                Task.reviewed_at.is_not(None),
                Task.reviewed_at >= start_utc,
                Task.reviewed_at < end_utc,
            )
        )
    )

    spent_sec = sum(t.spent_sec or 0 for t in finished)
    daily = _daily_breakdown(finished, monday)
    subjects = [
        {"subject": s, "done": n}
        for s, n in Counter(t.subject for t in finished).most_common()
    ]

    return {
        "week": f"{monday.isocalendar()[0]}-W{monday.isocalendar()[1]:02d}",
        "start": monday.isoformat(),
        "end": sunday.isoformat(),
        "tasks": {
            "planned": planned_total,
            "completed": planned_done,
            "rate": round(planned_done / planned_total, 3) if planned_total else None,
            "done_this_week": len(finished),
            "spent_min": round(spent_sec / 60),
        },
        "stars": _star_stats(db, child_id, start_utc, end_utc),
        "daily": daily,
        "subjects": subjects,
        "mistakes": _mistake_stats(db, child_id, start_utc, end_utc),
        "calc": _calc_stats(db, child_id, start_utc, end_utc),
    }


def _planned_stats(db: Session, child_id: int, monday: date, sunday: date) -> tuple[int, int]:
    """本周布置了多少、其中完成了多少。"""
    base = (
        Task.child_id == child_id,
        Task.deleted_at.is_(None),
        Task.task_date >= monday,
        Task.task_date <= sunday,
    )
    total = int(db.scalar(select(func.count()).select_from(Task).where(*base)) or 0)
    done = int(
        db.scalar(
            select(func.count()).select_from(Task).where(*base, Task.status == "done")
        ) or 0
    )
    return total, done


def _daily_breakdown(finished: list[Task], monday: date) -> list[dict]:
    """七天分布。已完成任务一周几十条，取回在 Python 里分组比七次 count 查询清楚。"""
    done_by_day: Counter[date] = Counter()
    spent_by_day: Counter[date] = Counter()
    for t in finished:
        d = local_date(t.reviewed_at)
        done_by_day[d] += 1
        spent_by_day[d] += t.spent_sec or 0

    out = []
    for i in range(7):
        d = monday + timedelta(days=i)
        out.append({
            "date": d.isoformat(),
            "weekday": WEEKDAY_CN[i],
            "done": done_by_day.get(d, 0),
            "spent_min": round(spent_by_day.get(d, 0) / 60),
        })
    return out


def _star_stats(db: Session, child_id: int, start_utc, end_utc) -> dict:
    rows = db.execute(
        select(StarLedger.delta).where(
            StarLedger.child_id == child_id,
            StarLedger.created_at >= start_utc,
            StarLedger.created_at < end_utc,
        )
    ).scalars().all()
    earned = sum(d for d in rows if d > 0)
    spent = -sum(d for d in rows if d < 0)
    return {
        "earned": earned,
        "spent": spent,
        "net": earned - spent,
        "balance": star_service.balance(db, child_id),
    }


def _mistake_stats(db: Session, child_id: int, start_utc, end_utc) -> dict:
    added = int(
        db.scalar(
            select(func.count()).select_from(Mistake).where(
                Mistake.child_id == child_id,
                Mistake.deleted_at.is_(None),
                Mistake.created_at >= start_utc,
                Mistake.created_at < end_utc,
            )
        ) or 0
    )
    # mistake_log 没有 child_id，只能 join 回 mistake 才能按孩子统计
    mastered = int(
        db.scalar(
            select(func.count())
            .select_from(MistakeLog)
            .join(Mistake, Mistake.id == MistakeLog.mistake_id)
            .where(
                Mistake.child_id == child_id,
                MistakeLog.action == "master",
                MistakeLog.created_at >= start_utc,
                MistakeLog.created_at < end_utc,
            )
        ) or 0
    )
    due = int(
        db.scalar(
            select(func.count()).select_from(Mistake).where(
                Mistake.child_id == child_id,
                Mistake.deleted_at.is_(None),
                Mistake.mastered.is_(False),
                Mistake.due_date.is_not(None),
                Mistake.due_date <= local_today(),
            )
        ) or 0
    )
    return {"added": added, "mastered": mastered, "due": due}


def _calc_stats(db: Session, child_id: int, start_utc, end_utc) -> dict:
    row = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(CalcRecord.total), 0),
            func.coalesce(func.sum(CalcRecord.right_count), 0),
            func.coalesce(func.sum(CalcRecord.seconds), 0),
        ).where(
            CalcRecord.child_id == child_id,
            CalcRecord.status == "done",
            CalcRecord.created_at >= start_utc,
            CalcRecord.created_at < end_utc,
        )
    ).one()
    rounds, questions, right, seconds = (int(x or 0) for x in row)
    return {
        "rounds": rounds,
        "questions": questions,
        "accuracy": round(right / questions, 3) if questions else None,
        "spent_min": round(seconds / 60),
    }
