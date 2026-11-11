"""M4：星星余额、兑换流转、周报口径。

重点覆盖四件容易写错、且错了不容易被发现的事：

1. 余额是 SUM 出来的，pending 必须占住余额
2. 批准才扣星 —— pending 期间余额一分不动
3. 批准前要按「排除自己」的口径重算一次，否则账目被外部改动后会透支
4. 周报的两组数字口径不同，完成率不能被补做拉过 100%
"""
from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.clock import local_today
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models import StarLedger, Task
from app.models.base import utcnow

PREFIX = "/api/v1"


def _seed_stars(child_id: int, entries: list[tuple[int, str]]) -> None:
    """直接写流水，用来快速把余额摆到想要的数。"""
    with SessionLocal() as db:
        for delta, reason in entries:
            db.add(StarLedger(
                child_id=child_id, delta=delta, reason=reason, ref_type="manual",
            ))
        db.commit()


def _stars(c) -> dict:
    r = c.get(f"{PREFIX}/stars")
    assert r.status_code == 200, r.text
    return r.json()


def _make_reward(c, name: str = "看动画片 20 分钟", cost: int = 10) -> dict:
    r = c.post(f"{PREFIX}/rewards", json={"name": name, "cost": cost})
    assert r.status_code == 200, r.text
    return r.json()


def _redeem(c, reward_id: int) -> dict:
    r = c.post(f"{PREFIX}/rewards/{reward_id}/redeem", json={})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- 余额口径

def test_balance_is_sum_of_ledger(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(5, "完成任务"), (3, "家长补发"), (-2, "兑换奖励")])
    s = _stars(c)
    assert s["balance"] == 6
    assert s["available"] == 6
    assert s["pending"] == 0
    assert [e["delta"] for e in s["ledger"]] == [-2, 3, 5]  # 按时间倒序


def test_pending_reserves_balance_but_does_not_move_it(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=8)
    _redeem(c, rw["id"])

    s = _stars(c)
    assert s["balance"] == 10, "待确认期间不能真扣星"
    assert s["pending"] == 8
    assert s["available"] == 2


def test_redeem_blocked_when_insufficient(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(5, "家长补发")])
    rw = _make_reward(c, cost=10)
    r = c.post(f"{PREFIX}/rewards/{rw['id']}/redeem", json={})
    assert r.status_code == 400
    assert r.json()["code"] == "insufficient_stars"


def test_second_redeem_blocked_by_first_pending(auth_client):
    """两笔 pending 叠加后超过余额，第二笔在申请阶段就该被挡住。"""
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=6)
    _redeem(c, rw["id"])

    r = c.post(f"{PREFIX}/rewards/{rw['id']}/redeem", json={})
    assert r.status_code == 400, "可用只剩 4，第二笔 6 星不该通过"
    assert r.json()["code"] == "insufficient_stars"


# ---------------------------------------------------------------- 兑换流转

def test_approve_deducts_and_writes_ledger(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=8)
    row = _redeem(c, rw["id"])

    r = c.post(f"{PREFIX}/redemptions/{row['id']}/approve", json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    assert r.json()["decided_at"] is not None

    s = _stars(c)
    assert s["balance"] == 2
    assert s["pending"] == 0
    assert s["available"] == 2
    assert s["ledger"][0]["delta"] == -8
    assert s["ledger"][0]["ref_type"] == "redemption"


def test_approve_twice_is_conflict(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=4)
    row = _redeem(c, rw["id"])

    assert c.post(f"{PREFIX}/redemptions/{row['id']}/approve", json={}).status_code == 200
    r = c.post(f"{PREFIX}/redemptions/{row['id']}/approve", json={})
    assert r.status_code == 409
    assert _stars(c)["balance"] == 6, "重复批准不能扣两次"


def test_reject_keeps_balance_and_requires_note(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=5)
    row = _redeem(c, rw["id"])

    # 不写原因不给过
    assert c.post(f"{PREFIX}/redemptions/{row['id']}/reject", json={}).status_code == 422
    assert c.post(
        f"{PREFIX}/redemptions/{row['id']}/reject", json={"note": "   "}
    ).status_code == 422

    r = c.post(
        f"{PREFIX}/redemptions/{row['id']}/reject",
        json={"note": "这周先不看了，周末再说"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    s = _stars(c)
    assert s["balance"] == 10, "拒绝不扣星"
    assert s["pending"] == 0
    assert s["available"] == 10


def test_cancel_releases_reserved_stars(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=7)
    row = _redeem(c, rw["id"])
    assert _stars(c)["available"] == 3

    r = c.post(f"{PREFIX}/redemptions/{row['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"
    assert _stars(c)["available"] == 10, "撤回后占用的星星要放回来"


def test_approve_rechecks_balance_when_books_changed(auth_client):
    """账目被外部改动后（这里用直接插一条扣减流水模拟），
    批准时必须以「排除自己」的口径重算，否则会透支。"""
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=6)
    row = _redeem(c, rw["id"])

    # 模拟别处又扣了 8 颗：余额变 2，可用 = 2 - 6(自己) = -4
    _seed_stars(info["child_id"], [(-8, "家长扣罚")])

    r = c.post(f"{PREFIX}/redemptions/{row['id']}/approve", json={})
    assert r.status_code == 400
    assert r.json()["code"] == "insufficient_stars"
    assert _stars(c)["balance"] == 2, "失败时不能留下任何扣减"


def test_long_reward_name_is_truncated_in_ledger(auth_client):
    """star_ledger.reason 是 varchar(32)，奖励名最长 64。
    不截断会在提交时报 Data too long，而且是在 commit 才炸。"""
    c, info = auth_client
    _seed_stars(info["child_id"], [(100, "家长补发")])
    long_name = "看" * 64
    rw = _make_reward(c, name=long_name, cost=5)
    row = _redeem(c, rw["id"])

    r = c.post(f"{PREFIX}/redemptions/{row['id']}/approve", json={})
    assert r.status_code == 200, r.text
    assert len(_stars(c)["ledger"][0]["reason"]) <= 32


# ---------------------------------------------------------------- 家长补发

def test_adjust_positive_and_negative(auth_client):
    c, info = auth_client
    r = c.post(f"{PREFIX}/stars/adjust", json={"delta": 5, "reason": "主动整理书桌"})
    assert r.status_code == 200
    assert r.json()["balance"] == 5

    r = c.post(f"{PREFIX}/stars/adjust", json={"delta": -3, "reason": "超时未收玩具"})
    assert r.json()["balance"] == 2


def test_adjust_zero_rejected(auth_client):
    c, _ = auth_client
    r = c.post(f"{PREFIX}/stars/adjust", json={"delta": 0})
    assert r.status_code == 400
    assert r.json()["code"] == "zero_delta"


def test_adjust_cannot_go_negative(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(3, "家长补发")])
    r = c.post(f"{PREFIX}/stars/adjust", json={"delta": -5})
    assert r.status_code == 400
    assert r.json()["code"] == "insufficient_stars"


def test_adjust_counts_pending_as_reserved(auth_client):
    """扣罚要看可用余额：待确认的兑换已经把那部分星星占住了。"""
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=8)
    _redeem(c, rw["id"])

    r = c.post(f"{PREFIX}/stars/adjust", json={"delta": -5})
    assert r.status_code == 400, "账面 10 颗但只有 2 颗可用，扣 5 会透支"


# ---------------------------------------------------------------- 奖励清单

def test_reward_crud(auth_client):
    c, _ = auth_client
    rw = _make_reward(c, name="玩 30 分钟", cost=15)
    assert rw["affordable"] is False

    r = c.patch(f"{PREFIX}/rewards/{rw['id']}", json={"cost": 3})
    assert r.status_code == 200
    assert r.json()["cost"] == 3

    assert c.patch(f"{PREFIX}/rewards/{rw['id']}", json={"status": "off"}).json()["status"] == "off"
    assert c.get(f"{PREFIX}/rewards?status=on").json() == []

    assert c.delete(f"{PREFIX}/rewards/{rw['id']}").status_code == 204
    assert len(c.get(f"{PREFIX}/rewards").json()) == 0


def test_off_reward_cannot_be_redeemed(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(50, "家长补发")])
    rw = _make_reward(c, cost=5)
    c.patch(f"{PREFIX}/rewards/{rw['id']}", json={"status": "off"})

    r = c.post(f"{PREFIX}/rewards/{rw['id']}/redeem", json={})
    assert r.status_code == 400
    assert r.json()["code"] == "reward_off"


def test_price_change_does_not_rewrite_history(auth_client):
    """改价后，已提交的申请仍按当时的价格结算。"""
    c, info = auth_client
    _seed_stars(info["child_id"], [(20, "家长补发")])
    rw = _make_reward(c, cost=6)
    row = _redeem(c, rw["id"])

    c.patch(f"{PREFIX}/rewards/{rw['id']}", json={"cost": 18})
    assert c.get(f"{PREFIX}/redemptions?status=pending").json()[0]["cost"] == 6

    c.post(f"{PREFIX}/redemptions/{row['id']}/approve", json={})
    assert _stars(c)["balance"] == 14, "按申请时的 6 颗扣，不是改后的 18 颗"


def test_deleting_reward_keeps_redemption_history(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(20, "家长补发")])
    rw = _make_reward(c, cost=6)
    row = _redeem(c, rw["id"])

    assert c.delete(f"{PREFIX}/rewards/{rw['id']}").status_code == 204
    hist = c.get(f"{PREFIX}/redemptions").json()
    assert len(hist) == 1
    assert hist[0]["reward_id"] is None, "外键 SET NULL"
    assert hist[0]["reward_name"] == "看动画片 20 分钟", "名称快照还在，账目不能断"
    assert hist[0]["status"] == "pending"

    # 快照完整的记录仍然可以正常批准
    assert c.post(f"{PREFIX}/redemptions/{row['id']}/approve", json={}).status_code == 200


def test_cross_account_cannot_touch_reward(auth_client, account_factory):
    """另一个账号看不到、也动不了别人家的奖励与兑换。"""
    c, info = auth_client
    _seed_stars(info["child_id"], [(10, "家长补发")])
    rw = _make_reward(c, cost=5)
    row = _redeem(c, rw["id"])

    # 第二个账号直接签一个 token 塞进 Cookie，省掉再走一次登录
    other = account_factory()
    c2 = TestClient(app)
    c2.cookies.set(settings.SESSION_COOKIE, create_access_token(str(other["account_id"])))

    assert c2.post(f"{PREFIX}/redemptions/{row['id']}/approve", json={}).status_code == 403
    assert c2.post(f"{PREFIX}/redemptions/{row['id']}/reject", json={"note": "x"}).status_code == 403
    assert c2.patch(f"{PREFIX}/rewards/{rw['id']}", json={"cost": 1}).status_code == 403
    assert c2.delete(f"{PREFIX}/rewards/{rw['id']}").status_code == 403
    assert c2.get(f"{PREFIX}/redemptions").json() == [], "看不到别人家的兑换"
    assert c2.get(f"{PREFIX}/stars").json()["balance"] == 0


# ---------------------------------------------------------------- 周报

def _done_task(child_id: int, task_date, reviewed_at, subject="数学", spent=600) -> int:
    with SessionLocal() as db:
        t = Task(
            child_id=child_id, subject=subject, title="周报测试任务",
            kind="homework", task_date=task_date, minutes_est=10, stars=2,
            status="done", reviewed_at=reviewed_at, spent_sec=spent,
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        return t.id


def test_weekly_separates_planned_from_finished(auth_client):
    """上周布置、本周补完的任务：算进「本周完成」，不算进「本周布置」。
    否则完成率会被补做拉到 100% 以上。"""
    c, info = auth_client
    today = local_today()
    now = utcnow()

    _done_task(info["child_id"], today, now)                    # 本周布置 + 本周完成
    _done_task(info["child_id"], today - timedelta(days=7), now)  # 上周布置 + 本周完成

    with SessionLocal() as db:
        db.add(Task(
            child_id=info["child_id"], subject="语文", title="还没做的",
            kind="homework", task_date=today, minutes_est=10, stars=1,
        ))
        db.commit()

    r = c.get(f"{PREFIX}/reports/weekly")
    assert r.status_code == 200, r.text
    w = r.json()

    assert w["tasks"]["planned"] == 2, "本周只布置了两条"
    assert w["tasks"]["completed"] == 1
    assert w["tasks"]["done_this_week"] == 2, "补做上周那条也算本周产出"
    assert w["tasks"]["rate"] == 0.5
    assert w["tasks"]["spent_min"] == 20
    assert sum(d["done"] for d in w["daily"]) == 2
    assert len(w["daily"]) == 7
    assert {s["subject"] for s in w["subjects"]} == {"数学"}
    assert w["stars"]["earned"] == 0


def test_weekly_stars_and_calc(auth_client):
    c, info = auth_client
    _seed_stars(info["child_id"], [(6, "完成任务"), (-2, "兑换奖励")])

    r = c.get(f"{PREFIX}/reports/weekly")
    w = r.json()
    assert w["stars"]["earned"] == 6
    assert w["stars"]["spent"] == 2
    assert w["stars"]["net"] == 4
    assert w["stars"]["balance"] == 4
    assert w["calc"]["rounds"] == 0


def test_weekly_empty_week_has_null_rate(auth_client):
    c, _ = auth_client
    w = c.get(f"{PREFIX}/reports/weekly").json()
    assert w["tasks"]["planned"] == 0
    assert w["tasks"]["rate"] is None, "没布置任务时不能除零"


def test_weekly_rejects_bad_week_format(auth_client):
    c, _ = auth_client
    assert c.get(f"{PREFIX}/reports/weekly?week=2026-45").status_code == 422
    assert c.get(f"{PREFIX}/reports/weekly?week=abc").status_code == 422


def test_weekly_can_query_past_week(auth_client):
    c, _ = auth_client
    today = local_today()
    last_week_day = today - timedelta(days=7)
    iso = last_week_day.isocalendar()
    w = c.get(f"{PREFIX}/reports/weekly?week={iso[0]}-W{iso[1]:02d}").json()
    assert w["week"] == f"{iso[0]}-W{iso[1]:02d}"
