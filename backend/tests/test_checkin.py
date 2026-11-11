"""M4c：打卡日历。

重点覆盖五个容易写错的口径：

1. **今天没打卡不算断。** 结算在 23:55，孩子白天打开日历时今天必然是空格，
   连续天数不能因此显示成 0。
2. **断一天就归零。** 昨天没打、前天打了，连续是 0 而不是 1。
3. **结算必须幂等。** 定时任务和孩子点开日历都会触发，两边撞上只能有一行。
4. **有任务但没做完不算打卡。** 「一个任务都没有」同样不算。
5. **日历要能区分「没做完」和「没布置」。** 否则连续断了孩子不知道原因。
"""
from calendar import monthrange
from datetime import date, timedelta

from app.core.clock import local_today
from app.core.db import SessionLocal
from app.models import Checkin, Task

PREFIX = "/api/v1"


def _seed_checkins(child_id: int, days: list[date]) -> None:
    """直接写打卡记录。历史日期没法用接口造，只能落库。"""
    with SessionLocal() as db:
        for d in days:
            db.add(Checkin(child_id=child_id, check_date=d))
        db.commit()


def _seed_tasks(child_id: int, days: list[date], status: str = "done") -> None:
    with SessionLocal() as db:
        for d in days:
            db.add(Task(
                child_id=child_id, subject="数学", title=f"口算 · {d}",
                kind="homework", source="manual", task_date=d,
                minutes_est=10, stars=1, status=status,
            ))
        db.commit()


def _calendar(c, month: str | None = None) -> dict:
    params = {"month": month} if month else {}
    r = c.get(f"{PREFIX}/checkins", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _settle(c):
    return c.post(f"{PREFIX}/checkins/settle")


# ---------------------------------------------------------------- 统计口径

def test_empty_calendar(auth_client):
    """没有任何打卡时四个数字都是 0，日历仍然返回整月格子。"""
    c, _ = auth_client
    data = _calendar(c)

    assert data["streak"] == 0
    assert data["longest"] == 0
    assert data["total"] == 0
    assert data["checked_today"] is False

    today = local_today()
    assert len(data["days"]) == monthrange(today.year, today.month)[1]
    assert data["days"][0]["date"] == today.replace(day=1).isoformat()


def test_streak_counts_back_from_today(auth_client):
    """今天已打卡，连续 3 天。"""
    c, info = auth_client
    today = local_today()
    _seed_checkins(info["child_id"], [today - timedelta(days=i) for i in range(3)])

    data = _calendar(c)
    assert data["streak"] == 3
    assert data["checked_today"] is True


def test_today_unsettled_does_not_break_streak(auth_client):
    """今天还没打卡是常态（结算在 23:55），连续要从昨天起算而不是归零。"""
    c, info = auth_client
    today = local_today()
    _seed_checkins(info["child_id"], [today - timedelta(days=i) for i in (1, 2)])

    data = _calendar(c)
    assert data["streak"] == 2
    assert data["checked_today"] is False


def test_gap_resets_streak(auth_client):
    """昨天断了，连续就是 0——前天打过的卡不续上。"""
    c, info = auth_client
    today = local_today()
    _seed_checkins(info["child_id"], [today - timedelta(days=i) for i in (2, 3, 4)])

    data = _calendar(c)
    assert data["streak"] == 0
    assert data["total"] == 3


def test_longest_survives_break(auth_client):
    """历史最长不会被后面的断档抹掉。"""
    c, info = auth_client
    today = local_today()
    # 中间断一天：4 天连击 → 断 → 2 天连击
    days = [today - timedelta(days=i) for i in range(9, 5, -1)]
    days += [today - timedelta(days=i) for i in (1, 2)]
    _seed_checkins(info["child_id"], days)

    data = _calendar(c)
    assert data["streak"] == 2      # 当前是最近那 2 天
    assert data["longest"] == 4     # 最长仍然是前面那一段
    assert data["total"] == 6


# ---------------------------------------------------------------- 结算

def test_settle_requires_all_tasks_done(auth_client):
    """还有任务没做完，不能打卡。"""
    c, info = auth_client
    today = local_today()
    _seed_tasks(info["child_id"], [today], status="doing")

    r = _settle(c)
    assert r.status_code == 200, r.text
    assert r.json()["created"] is False
    assert r.json()["checked_today"] is False
    assert _calendar(c)["streak"] == 0


def test_settle_requires_at_least_one_task(auth_client):
    """今天压根没布置任务，也不算打卡日。"""
    c, _ = auth_client
    r = _settle(c)
    assert r.status_code == 200, r.text
    assert r.json()["created"] is False


def test_settle_when_all_done(auth_client):
    """任务全部完成 → 当场补记，不用等 23:55。"""
    c, info = auth_client
    today = local_today()
    _seed_tasks(info["child_id"], [today], status="done")
    _seed_checkins(info["child_id"], [today - timedelta(days=1)])  # 昨天已打

    r = _settle(c)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    assert body["checked_today"] is True
    assert body["streak"] == 2      # 昨天 + 今天


def test_settle_is_idempotent(auth_client):
    """定时任务与接口可能同时触发，重复调用只能有一行。"""
    c, info = auth_client
    today = local_today()
    _seed_tasks(info["child_id"], [today], status="done")

    first = _settle(c).json()
    second = _settle(c).json()

    assert first["created"] is True
    assert second["created"] is False
    assert second["checked_today"] is True
    assert _calendar(c)["total"] == 1


def test_settle_ignores_soft_deleted_task(auth_client):
    """删掉的任务不该拦住打卡。"""
    c, info = auth_client
    today = local_today()
    _seed_tasks(info["child_id"], [today], status="done")
    with SessionLocal() as db:
        t = db.query(Task).filter(Task.child_id == info["child_id"]).first()
        t.deleted_at = t.created_at
        db.commit()

    assert _settle(c).json()["created"] is False


# ---------------------------------------------------------------- 日历格子

def test_calendar_marks_task_days_separately(auth_client):
    """日历要区分「有任务没做完」和「那天没布置」。"""
    c, info = auth_client
    today = local_today()
    first = today.replace(day=1)
    _seed_tasks(info["child_id"], [first], status="todo")
    _seed_checkins(info["child_id"], [today])

    data = _calendar(c)
    by_date = {d["date"]: d for d in data["days"]}

    assert by_date[first.isoformat()] == {
        "date": first.isoformat(), "checked": False, "has_task": True,
    }
    assert by_date[today.isoformat()]["checked"] is True
    assert by_date[today.isoformat()]["has_task"] is False


def test_calendar_first_weekday(auth_client):
    """first_weekday 是排格子用的，必须是 1=周一 … 7=周日。"""
    c, _ = auth_client
    data = _calendar(c, "2026-11")
    assert data["month"] == "2026-11"
    assert data["first_weekday"] == date(2026, 11, 1).isoweekday() == 7
    assert len(data["days"]) == 30


def test_calendar_previous_month(auth_client):
    """可以翻到上个月看，格子数与月份长度对得上。"""
    c, _ = auth_client
    data = _calendar(c, "2026-02")
    assert data["month"] == "2026-02"
    assert len(data["days"]) == 28       # 2026 不是闰年


def test_bad_month_rejected(auth_client):
    """月份格式错误返回 400，不是 500。"""
    c, _ = auth_client
    for bad in ("2026-13", "202611", "2026-11-05", "abc"):
        r = c.get(f"{PREFIX}/checkins", params={"month": bad})
        assert r.status_code == 400, f"{bad} → {r.status_code}"
