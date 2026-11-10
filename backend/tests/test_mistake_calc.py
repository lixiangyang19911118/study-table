"""M3：错题的间隔重复 + 口算的出题判分。

重点覆盖三件容易写错、且错了不容易被发现的事：
1. 间隔表 1/2/4/7 与「连对 4 次掌握」的边界
2. 答错必须回到起点，而不是退一格
3. 出题响应里绝不能带答案
"""
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.clock import local_today
from app.core.db import SessionLocal
from app.models import CalcRecord, Mistake, StarLedger, Task, TaskReview
from app.tasks import jobs

PREFIX = "/api/v1"


def _make_mistake(c, **over) -> dict:
    body = {"subject": "数学", "point": "两位数进位加法", "stem": "37 + 25 = ?",
            "answer_own": "52", "answer_right": "62", "cause": "计算错"}
    body.update(over)
    r = c.post(f"{PREFIX}/mistakes", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _redo_task(child_id: int, mistake_id: int) -> int:
    """直接插一条「错题重做」任务。POST /tasks 不允许指定 kind/source，
    而扫描器要到明天零点才跑，测试里只能自己造。"""
    with SessionLocal() as db:
        t = Task(
            child_id=child_id, subject="数学", title="错题重做 · 两位数进位加法",
            kind="redo", source="mistake", source_ref=f"mistake:{mistake_id}",
            task_date=local_today(), minutes_est=8, stars=2,
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        return t.id


# ---------------------------------------------------------------- 错题录入


def test_create_sets_tomorrow_and_zero_stage(auth_client):
    c, info = auth_client
    m = _make_mistake(c)
    assert m["stage"] == 0
    assert m["mastered"] is False
    assert m["due_date"] == (local_today() + timedelta(days=1)).isoformat()
    assert m["source"] == "manual"
    assert m["review_count"] == 0
    assert [log["action"] for log in m["logs"]] == ["add"]


def test_create_requires_stem_or_photo(auth_client):
    c, _ = auth_client
    r = c.post(f"{PREFIX}/mistakes", json={"subject": "数学", "stem": "   "})
    assert r.status_code == 400
    assert r.json()["code"] == "empty_mistake"


def test_create_rejects_unknown_cause(auth_client):
    c, _ = auth_client
    r = c.post(f"{PREFIX}/mistakes", json={"stem": "1+1", "cause": "心情不好"})
    assert r.status_code == 422


# ---------------------------------------------------------------- 间隔推进


def test_four_correct_reviews_master_it(auth_client):
    """连对 4 次 → 掌握，且中途每次的间隔符合 1/2/4/7。"""
    c, info = auth_client
    m = _make_mistake(c)
    mid = m["id"]
    today = local_today()

    # 用服务层直接推进：接口层的入口是「审核错题重做任务」，那条路在
    # test_approve_advances_mistake 里单独测，这里只盯节奏。
    from app.services import mistake_service
    from app.core.db import SessionLocal

    expected_gaps = [2, 4, 7]     # 第 1、2、3 次答对之后的下次间隔
    with SessionLocal() as db:
        obj = db.get(Mistake, mid)
        for i, gap in enumerate(expected_gaps):
            obj = mistake_service.review(db, obj, True)
            assert obj.stage == i + 1
            assert obj.mastered is False
            assert obj.due_date == today + timedelta(days=gap), f"第 {i + 1} 次后间隔错了"

        obj = mistake_service.review(db, obj, True)
        assert obj.stage == 4
        assert obj.mastered is True
        assert obj.due_date is None

    # 流水应有 add + 4 条 redo
    detail = c.get(f"{PREFIX}/mistakes/{mid}").json()
    actions = [log["action"] for log in detail["logs"]]
    assert actions == ["add", "redo", "redo", "redo", "redo"]
    assert all(log["is_correct"] for log in detail["logs"][1:])


def test_wrong_review_resets_to_start(auth_client):
    """答错回到起点，不是退一格。"""
    c, _ = auth_client
    m = _make_mistake(c)
    from app.services import mistake_service

    with SessionLocal() as db:
        obj = db.get(Mistake, m["id"])
        obj = mistake_service.review(db, obj, True)
        obj = mistake_service.review(db, obj, True)
        assert obj.stage == 2

        obj = mistake_service.review(db, obj, False)
        assert obj.stage == 0
        assert obj.due_date == local_today() + timedelta(days=1)
        assert obj.mastered is False


def test_review_on_mastered_is_rejected(auth_client):
    c, _ = auth_client
    m = _make_mistake(c)
    assert c.post(f"{PREFIX}/mistakes/{m['id']}/master").status_code == 200

    from app.services import mistake_service

    with SessionLocal() as db:
        obj = db.get(Mistake, m["id"])
        with pytest.raises(mistake_service.MistakeError) as e:
            mistake_service.review(db, obj, True)
        assert e.value.code == "already_mastered"


def test_master_and_reopen(auth_client):
    c, _ = auth_client
    m = _make_mistake(c)

    r = c.post(f"{PREFIX}/mistakes/{m['id']}/master").json()
    assert r["mastered"] is True and r["stage"] == 4 and r["due_date"] is None

    r = c.post(f"{PREFIX}/mistakes/{m['id']}/reopen").json()
    assert r["mastered"] is False and r["stage"] == 0
    assert r["due_date"] == (local_today() + timedelta(days=1)).isoformat()


# ---------------------------------------------------------------- 列表与计数


def test_categories_and_counts(auth_client):
    c, _ = auth_client
    a = _make_mistake(c)
    b = _make_mistake(c, stem="18 - 9 = ?")
    c.post(f"{PREFIX}/mistakes/{b['id']}/master")

    counts = c.get(f"{PREFIX}/mistakes/counts").json()
    assert counts == {"learning": 1, "due": 0, "mastered": 1}

    learning = c.get(f"{PREFIX}/mistakes?category=learning").json()
    assert [x["id"] for x in learning] == [a["id"]]

    mastered = c.get(f"{PREFIX}/mistakes?category=mastered").json()
    assert [x["id"] for x in mastered] == [b["id"]]

    # 明天还没到，今天不该有到期
    assert c.get(f"{PREFIX}/mistakes?category=due").json() == []


def test_soft_deleted_mistake_disappears(auth_client):
    c, _ = auth_client
    m = _make_mistake(c)
    assert c.delete(f"{PREFIX}/mistakes/{m['id']}").status_code == 204
    assert c.get(f"{PREFIX}/mistakes?category=learning").json() == []
    assert c.get(f"{PREFIX}/mistakes/{m['id']}").status_code == 404


def test_cannot_read_other_account_mistake(auth_client, account_factory):
    c, _ = auth_client
    m = _make_mistake(c)

    other = account_factory()
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.conftest import PASSWORD

    c2 = TestClient(app)
    r = c2.post(f"{PREFIX}/auth/login",
                json={"username": other["username"], "password": PASSWORD})
    assert r.status_code == 200

    assert c2.get(f"{PREFIX}/mistakes/{m['id']}").status_code == 403


# ---------------------------------------------------------------- 与任务的衔接


def test_scan_generates_redo_task(auth_client):
    """到期错题被扫描器转成今日任务。"""
    c, info = auth_client
    m = _make_mistake(c)

    # 造一道「昨天就该复习」的错题
    with SessionLocal() as db:
        obj = db.get(Mistake, m["id"])
        obj.due_date = local_today() - timedelta(days=1)
        db.commit()

    created = jobs.scan_due_mistakes()
    assert created >= 1

    with SessionLocal() as db:
        task = db.scalar(
            select(Task).where(Task.source_ref == f"mistake:{m['id']}")
        )
        assert task is not None
        assert task.kind == "redo"
        assert task.status == "todo"
        assert task.task_date == local_today()

    # 再扫一次不应重复生成（幂等）
    jobs.scan_due_mistakes()
    with SessionLocal() as db:
        rows = db.scalars(select(Task).where(Task.source_ref == f"mistake:{m['id']}")).all()
        assert len(rows) == 1, "同一天同一道错题只能有一条任务"


def test_approve_advances_mistake(auth_client):
    """审核错题重做任务时判「做对了」，错题推进一轮。"""
    c, info = auth_client
    m = _make_mistake(c)
    tid = _redo_task(info["child_id"], m["id"])

    c.post(f"{PREFIX}/tasks/{tid}/start")
    c.post(f"{PREFIX}/tasks/{tid}/submit", json={"note": "重做了一遍"})
    r = c.post(f"{PREFIX}/tasks/{tid}/approve", json={"redo_correct": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "done"
    assert body["mistake"]["id"] == m["id"]

    detail = c.get(f"{PREFIX}/mistakes/{m['id']}").json()
    assert detail["stage"] == 1
    assert detail["review_count"] == 1
    assert detail["due_date"] == (local_today() + timedelta(days=2)).isoformat()


def test_approve_wrong_answer_resets(auth_client):
    c, info = auth_client
    m = _make_mistake(c)
    tid = _redo_task(info["child_id"], m["id"])

    c.post(f"{PREFIX}/tasks/{tid}/start")
    c.post(f"{PREFIX}/tasks/{tid}/submit", json={"note": "还是不会"})
    r = c.post(f"{PREFIX}/tasks/{tid}/approve", json={"redo_correct": False})
    assert r.status_code == 200

    detail = c.get(f"{PREFIX}/mistakes/{m['id']}").json()
    assert detail["stage"] == 0
    assert detail["due_date"] == (local_today() + timedelta(days=1)).isoformat()


def test_approve_without_judgement_leaves_mistake_alone(auth_client):
    """不传 redo_correct 就只完成任务，不动节奏——留给「先收星星，回头再判」的场景。"""
    c, info = auth_client
    m = _make_mistake(c)
    tid = _redo_task(info["child_id"], m["id"])

    c.post(f"{PREFIX}/tasks/{tid}/start")
    c.post(f"{PREFIX}/tasks/{tid}/submit", json={"note": "做完了"})
    assert c.post(f"{PREFIX}/tasks/{tid}/approve").status_code == 200

    detail = c.get(f"{PREFIX}/mistakes/{m['id']}").json()
    assert detail["stage"] == 0
    assert detail["review_count"] == 0


def test_redo_correct_on_normal_task_is_rejected(auth_client):
    c, _ = auth_client
    r = c.post(f"{PREFIX}/tasks", json={"title": "抄写生字", "subject": "语文", "stars": 1})
    tid = r.json()["id"]
    c.post(f"{PREFIX}/tasks/{tid}/start")
    c.post(f"{PREFIX}/tasks/{tid}/submit", json={"note": "写完了"})

    resp = c.post(f"{PREFIX}/tasks/{tid}/approve", json={"redo_correct": True})
    assert resp.status_code == 400


# ---------------------------------------------------------------- 口算：出题


def test_round_never_leaks_answers(auth_client):
    c, _ = auth_client
    r = c.post(f"{PREFIX}/calc/rounds", json={"count": 10, "range_max": 20})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["total"] == 10
    assert data["status"] == "doing"
    assert len(data["questions"]) == 10

    raw = r.text
    assert '"answer"' not in raw, "出题响应里出现了 answer 字段"
    for q in data["questions"]:
        assert set(q) == {"index", "type", "stem"}, f"题目字段多了：{q.keys()}"

    # 库里必须有答案，否则根本没法判分
    with SessionLocal() as db:
        rec = db.get(CalcRecord, data["id"])
        assert rec.questions and all("answer" in q for q in rec.questions)


def test_generate_validates_input(auth_client):
    c, _ = auth_client
    # 题数越界被 schema 挡下（ge=5 / le=50），返回 422
    assert c.post(f"{PREFIX}/calc/rounds", json={"count": 3}).status_code == 422
    # 范围与题型是业务校验，返回 400
    assert c.post(f"{PREFIX}/calc/rounds", json={"range_max": 30}).status_code == 400
    assert c.post(f"{PREFIX}/calc/rounds",
                  json={"types": ["divide"]}).status_code == 400


# ---------------------------------------------------------------- 口算：判分


def _answers_from_db(round_id: int, wrong: int = 0) -> list[str]:
    with SessionLocal() as db:
        rec = db.get(CalcRecord, round_id)
        out = [str(q["answer"]) for q in rec.questions]
    for i in range(wrong):
        out[i] = "99999"
    return out


def test_submit_grades_per_question(auth_client):
    c, _ = auth_client
    rid = c.post(f"{PREFIX}/calc/rounds", json={"count": 10, "range_max": 20}).json()["id"]

    r = c.post(f"{PREFIX}/calc/rounds/{rid}/submit", json={"answers": _answers_from_db(rid, 3)})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["right_count"] == 7
    assert data["total"] == 10
    assert data["accuracy"] == pytest.approx(0.7)
    assert len(data["wrong"]) == 3
    assert data["wrong"][0]["right_answer"] != "99999"
    assert data["stars_earned"] == 0, "独立练习（无任务）不发星"


def test_full_marks_answer_accepts_fullwidth(auth_client):
    """全角数字要认。孩子用中文输入法敲出来的「１２」也是 12。"""
    c, _ = auth_client
    rid = c.post(f"{PREFIX}/calc/rounds", json={"count": 5, "range_max": 10}).json()["id"]

    with SessionLocal() as db:
        rec = db.get(CalcRecord, rid)
        full = {"0": "０", "1": "１", "2": "２", "3": "３", "4": "４",
                "5": "５", "6": "６", "7": "７", "8": "８", "9": "９"}
        answers = ["".join(full.get(ch, ch) for ch in str(q["answer"])) for q in rec.questions]

    data = c.post(f"{PREFIX}/calc/rounds/{rid}/submit", json={"answers": answers}).json()
    assert data["right_count"] == 5


def test_cannot_submit_twice(auth_client):
    c, _ = auth_client
    rid = c.post(f"{PREFIX}/calc/rounds", json={"count": 5}).json()["id"]
    answers = _answers_from_db(rid)
    assert c.post(f"{PREFIX}/calc/rounds/{rid}/submit",
                  json={"answers": answers}).status_code == 200
    second = c.post(f"{PREFIX}/calc/rounds/{rid}/submit", json={"answers": answers})
    assert second.status_code == 409


# ---------------------------------------------------------------- 口算：任务结算


def _calc_task(c, stars: int = 4) -> int:
    r = c.post(f"{PREFIX}/tasks", json={"title": "口算 10 题", "subject": "数学", "stars": stars})
    tid = r.json()["id"]
    with SessionLocal() as db:
        db.get(Task, tid).kind = "calc"
        db.commit()
    return tid


def test_calc_task_completes_and_pays_by_accuracy(auth_client):
    """10 题对 7，任务 4 星 → 实得 ceil(4*0.7)=3 星，任务直接 done。"""
    c, info = auth_client
    tid = _calc_task(c, stars=4)

    rid = c.post(f"{PREFIX}/calc/rounds",
                 json={"count": 10, "task_id": tid}).json()["id"]
    data = c.post(f"{PREFIX}/calc/rounds/{rid}/submit",
                  json={"answers": _answers_from_db(rid, 3)}).json()

    assert data["right_count"] == 7
    assert data["stars_earned"] == 3
    assert data["task"]["status"] == "done"

    with SessionLocal() as db:
        task = db.get(Task, tid)
        assert task.status == "done"
        # 机器判分不写 TaskReview：没有人在审，造假记录会让家长端出现幻觉
        assert db.scalar(
            select(TaskReview.id).where(TaskReview.task_id == tid)
        ) is None, "机器判分不该产生审核记录"
        total = db.scalar(
            select(StarLedger.delta).where(
                StarLedger.ref_type == "task", StarLedger.ref_id == tid
            )
        )
        assert total == 3


def test_all_wrong_pays_zero_but_still_completes(auth_client):
    c, _ = auth_client
    tid = _calc_task(c, stars=3)
    rid = c.post(f"{PREFIX}/calc/rounds", json={"count": 5, "task_id": tid}).json()["id"]
    data = c.post(f"{PREFIX}/calc/rounds/{rid}/submit",
                  json={"answers": ["99999"] * 5}).json()

    assert data["stars_earned"] == 0
    assert data["task"]["status"] == "done"

    with SessionLocal() as db:
        assert db.scalar(
            select(StarLedger.id).where(StarLedger.ref_id == tid)
        ) is None, "0 星不该写流水"


def test_calc_round_starts_task_automatically(auth_client):
    """孩子从列表点进任务直接做题，没点「开始」，出题时要补 start。"""
    c, _ = auth_client
    tid = _calc_task(c)
    c.post(f"{PREFIX}/calc/rounds", json={"count": 5, "task_id": tid})

    with SessionLocal() as db:
        task = db.get(Task, tid)
        assert task.status == "doing"
        assert task.started_at is not None


def test_round_on_non_calc_task_rejected(auth_client):
    c, _ = auth_client
    tid = c.post(f"{PREFIX}/tasks", json={"title": "抄写", "stars": 1}).json()["id"]
    r = c.post(f"{PREFIX}/calc/rounds", json={"count": 5, "task_id": tid})
    assert r.status_code == 400


# ---------------------------------------------------------------- 口算：错题入库


def test_to_mistakes_only_by_request(auth_client):
    """默认不入库，手动挑才进。挑进来的带 source=calc 与明天的复习日。"""
    c, _ = auth_client
    rid = c.post(f"{PREFIX}/calc/rounds", json={"count": 10, "range_max": 20}).json()["id"]
    c.post(f"{PREFIX}/calc/rounds/{rid}/submit", json={"answers": _answers_from_db(rid, 4)})

    # 交卷本身不产生错题
    assert c.get(f"{PREFIX}/mistakes?category=learning").json() == []

    r = c.post(f"{PREFIX}/calc/rounds/{rid}/to-mistakes", json={})
    assert r.status_code == 200
    assert r.json()["created"] == 4

    items = c.get(f"{PREFIX}/mistakes?category=learning").json()
    assert len(items) == 4
    assert all(m["source"] == "calc" for m in items)
    assert all(m["due_date"] == (local_today() + timedelta(days=1)).isoformat() for m in items)
    assert all(m["answer_right"] for m in items)


def test_to_mistakes_can_pick_indexes(auth_client):
    c, _ = auth_client
    rid = c.post(f"{PREFIX}/calc/rounds", json={"count": 10}).json()["id"]
    c.post(f"{PREFIX}/calc/rounds/{rid}/submit", json={"answers": _answers_from_db(rid, 5)})

    wrong = c.post(f"{PREFIX}/calc/rounds/{rid}/to-mistakes", json={}).json()
    assert wrong["created"] == 5
    # 再点一次全部，会重复入库——这是已知取舍：错题是快照，同题多录一条
    # 比漏录一条好，去重成本高于收益。此处只验证按题号挑的行为。
    rid2 = c.post(f"{PREFIX}/calc/rounds", json={"count": 10}).json()["id"]
    c.post(f"{PREFIX}/calc/rounds/{rid2}/submit", json={"answers": _answers_from_db(rid2, 3)})
    picked = c.post(f"{PREFIX}/calc/rounds/{rid2}/to-mistakes", json={"indexes": [0]}).json()
    assert picked["created"] == 1


def test_to_mistakes_requires_submitted(auth_client):
    c, _ = auth_client
    rid = c.post(f"{PREFIX}/calc/rounds", json={"count": 5}).json()["id"]
    assert c.post(f"{PREFIX}/calc/rounds/{rid}/to-mistakes", json={}).status_code == 409


def test_round_history(auth_client):
    c, _ = auth_client
    rid = c.post(f"{PREFIX}/calc/rounds", json={"count": 5}).json()["id"]
    c.post(f"{PREFIX}/calc/rounds/{rid}/submit", json={"answers": _answers_from_db(rid, 1)})

    rows = c.get(f"{PREFIX}/calc/rounds").json()
    assert len(rows) == 1
    assert rows[0]["id"] == rid
    assert rows[0]["right_count"] == 4
    assert rows[0]["accuracy"] == pytest.approx(0.8)
