"""M2 状态机。重点不是「能跑通」，是「不该通的都不通」。

三类断言：
1. 合法路径走得通，且副作用（流水、计时、清空）都对；
2. 非法路径必须 4xx，不能悄悄改成 500，也不能默默无视；
3. 并发/重复调用只生效一次——审核点两下只发一份星星。
"""
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select

from app.core.clock import local_today
from app.core.db import SessionLocal
from app.models import FileObject, StarLedger, TaskShot


@pytest.fixture
def make_file():
    """直接建 file_object，不走 /files 上传：测试不关心落盘，也不想往磁盘扔垃圾。"""
    created: list[int] = []

    def make(child_id: int, biz_type: str = "shot") -> int:
        with SessionLocal() as db:
            obj = FileObject(
                child_id=child_id,
                biz_type=biz_type,
                rel_path=f"uploads/shots/{uuid.uuid4().hex}.jpg",
                orig_name="pytest.jpg",
                mime="image/jpeg",
                size_bytes=8,
            )
            db.add(obj)
            db.commit()
            db.refresh(obj)
            created.append(obj.id)
            return obj.id

    yield make

    if not created:
        return
    with SessionLocal() as db:
        # task_shot.file_id 是 ON DELETE RESTRICT，先拆引用再删文件记录。
        # file_object.child_id 又是 SET NULL，账号级联删不掉它，只能自己收尾。
        db.execute(delete(TaskShot).where(TaskShot.file_id.in_(created)))
        db.execute(delete(FileObject).where(FileObject.id.in_(created)))
        db.commit()


def create_task(client, **overrides) -> dict:
    body = {"subject": "数学", "title": "口算 20 题", "minutes_est": 20, "stars": 2}
    body.update(overrides)
    r = client.post("/api/v1/tasks", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def balance(child_id: int) -> int:
    with SessionLocal() as db:
        return db.scalar(
            select(func.coalesce(func.sum(StarLedger.delta), 0)).where(
                StarLedger.child_id == child_id
            )
        )


def test_create_task_defaults(auth_client):
    client, _ = auth_client
    task = create_task(client)
    assert task["status"] == "todo"
    assert task["source"] == "manual"
    assert task["task_date"] == local_today().isoformat()
    assert task["spent_sec"] == 0
    assert task["shot_count"] == 0
    assert task["shots"] == []


def test_todo_cannot_submit(auth_client):
    """必须点过「开始」才能提交，否则计时永远是 0。"""
    client, _ = auth_client
    task = create_task(client)
    r = client.post(f"/api/v1/tasks/{task['id']}/submit")
    assert r.status_code == 409
    assert r.json()["code"] == "invalid_transition"


def test_start_then_submit_with_note_only(auth_client):
    """口头说明也能交——这是 M2 明确要求的「二选一」。"""
    client, _ = auth_client
    task = create_task(client)
    tid = task["id"]

    r = client.post(f"/api/v1/tasks/{tid}/start")
    assert r.status_code == 200
    assert r.json()["status"] == "doing"
    assert r.json()["started_at"] is not None

    r = client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "  读了三遍，录音发你了  "})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "submitted"
    assert body["submit_note"] == "读了三遍，录音发你了"     # 两端空白去掉
    assert 0 <= body["spent_sec"] < 60


def test_submit_needs_photo_or_note(auth_client):
    client, _ = auth_client
    task = create_task(client)
    client.post(f"/api/v1/tasks/{task['id']}/start")

    r = client.post(f"/api/v1/tasks/{task['id']}/submit")
    assert r.status_code == 400
    assert r.json()["code"] == "nothing_to_submit"

    # 只给空白也算没写
    r = client.post(f"/api/v1/tasks/{task['id']}/submit", json={"note": "   "})
    assert r.status_code == 400


def test_submit_with_photo_no_note(auth_client, make_file):
    client, info = auth_client
    task = create_task(client)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")

    file_id = make_file(info["child_id"])
    r = client.post(f"/api/v1/tasks/{tid}/shots", json={"file_id": file_id, "width": 1200, "height": 1600})
    assert r.status_code == 201, r.text
    assert r.json()["shot_count"] == 1
    assert r.json()["shots"][0]["url"] == f"/api/v1/files/{file_id}"

    r = client.post(f"/api/v1/tasks/{tid}/submit")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "submitted"
    assert r.json()["submit_note"] is None


def test_approve_awards_stars_exactly_once(auth_client):
    client, info = auth_client
    task = create_task(client, stars=3)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "做完了"})

    r = client.post(f"/api/v1/tasks/{tid}/approve")
    assert r.status_code == 200
    assert r.json()["status"] == "done"
    assert r.json()["reviewed_at"] is not None
    assert r.json()["reviews"][-1]["action"] == "approve"
    assert balance(info["child_id"]) == 3

    # 家长连点第二下：必须被状态机挡住，且不能再来一份星星
    r = client.post(f"/api/v1/tasks/{tid}/approve")
    assert r.status_code == 409
    assert balance(info["child_id"]) == 3


def test_reject_requires_reason(auth_client):
    client, _ = auth_client
    task = create_task(client)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "交了"})

    assert client.post(f"/api/v1/tasks/{tid}/reject", json={"comment": ""}).status_code == 422
    assert client.post(f"/api/v1/tasks/{tid}/reject", json={"comment": "   "}).status_code == 422

    r = client.post(f"/api/v1/tasks/{tid}/reject", json={"comment": "第 3 题漏了单位"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "rejected"
    assert body["reviews"][-1]["comment"] == "第 3 题漏了单位"
    assert body["submit_note"] is None      # 上一轮说明随退回作废


def test_reject_then_must_do_something_new(auth_client, make_file):
    """退回后原样再交一次必须被拦，否则退回就是个形式。"""
    client, info = auth_client
    task = create_task(client)
    tid = task["id"]
    file_id = make_file(info["child_id"])

    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/shots", json={"file_id": file_id})
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "第一次"})
    client.post(f"/api/v1/tasks/{tid}/reject", json={"comment": "重写"})

    # rejected 不能直接提交，必须先重做
    assert client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "改好了"}).status_code == 409

    assert client.post(f"/api/v1/tasks/{tid}/restart").json()["status"] == "doing"

    # 旧照片不算新东西，也没写说明 → 拦
    r = client.post(f"/api/v1/tasks/{tid}/submit")
    assert r.status_code == 400
    assert r.json()["code"] == "redo_nothing_new"

    # 写一句说明就放行
    r = client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "第 3 题补上单位了"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "submitted"


def test_withdraw_returns_to_doing(auth_client):
    client, _ = auth_client
    task = create_task(client)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "先交了"})

    r = client.post(f"/api/v1/tasks/{tid}/withdraw")
    assert r.status_code == 200
    assert r.json()["status"] == "doing"
    # 撤回后还能再交，且说明不会丢
    r = client.post(f"/api/v1/tasks/{tid}/submit")
    assert r.status_code == 200
    assert r.json()["submit_note"] == "先交了"


def test_done_is_terminal(auth_client):
    client, _ = auth_client
    task = create_task(client)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "ok"})
    client.post(f"/api/v1/tasks/{tid}/approve")

    # M2 不做撤销审核：done 没有出边
    for path in ("start", "restart", "withdraw"):
        assert client.post(f"/api/v1/tasks/{tid}/{path}").status_code == 409
    assert client.post(f"/api/v1/tasks/{tid}/reject", json={"comment": "x"}).status_code == 409
    assert client.delete(f"/api/v1/tasks/{tid}").status_code == 409
    assert client.patch(f"/api/v1/tasks/{tid}", json={"title": "改"}).status_code == 409


def test_soft_delete_hides_task(auth_client):
    client, _ = auth_client
    task = create_task(client)
    tid = task["id"]
    assert client.delete(f"/api/v1/tasks/{tid}").status_code == 204
    assert client.get(f"/api/v1/tasks/{tid}").status_code == 404
    assert [t["id"] for t in client.get("/api/v1/tasks").json()] == []


def test_submitted_cannot_be_deleted(auth_client):
    client, _ = auth_client
    task = create_task(client)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "ok"})
    assert client.delete(f"/api/v1/tasks/{tid}").status_code == 409


def test_shot_locked_after_submit(auth_client, make_file):
    client, info = auth_client
    task = create_task(client)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "ok"})

    r = client.post(
        f"/api/v1/tasks/{tid}/shots", json={"file_id": make_file(info["child_id"])}
    )
    assert r.status_code == 409
    assert r.json()["code"] == "shots_locked"


def test_foreign_task_is_forbidden(account_factory, client):
    """A 布置的任务，B 碰不到——包括审核发星这条最值钱的路径。"""
    client.post("/api/v1/auth/login", json={"username": "pytest_none", "password": "x"})
    a = account_factory(child_name="A 家娃")

    from tests.conftest import PASSWORD
    assert client.post(
        "/api/v1/auth/login", json={"username": a["username"], "password": PASSWORD}
    ).status_code == 200
    task = create_task(client)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "ok"})

    b = account_factory(child_name="B 家娃")
    assert client.post(
        "/api/v1/auth/login", json={"username": b["username"], "password": PASSWORD}
    ).status_code == 200

    assert client.post(f"/api/v1/tasks/{tid}/approve").status_code == 403
    assert client.get(f"/api/v1/tasks/{tid}").status_code == 403
    assert client.post(f"/api/v1/tasks/{tid}/shots", json={"file_id": 1}).status_code == 403
    assert balance(a["child_id"]) == 0


def test_backlog_is_derived_not_scheduled(auth_client):
    """逾期不是状态，是 task_date 算出来的。关机三天再打开，补做区依然对。"""
    client, _ = auth_client
    yesterday = (local_today() - timedelta(days=1)).isoformat()
    old = create_task(client, title="昨天没写完的", task_date=yesterday)
    today_task = create_task(client, title="今天的")

    today_ids = [t["id"] for t in client.get("/api/v1/tasks?bucket=today").json()]
    backlog_ids = [t["id"] for t in client.get("/api/v1/tasks?bucket=backlog").json()]
    assert today_ids == [today_task["id"]]
    assert backlog_ids == [old["id"]]
    # 逾期不改状态，孩子还能接着做
    assert client.get(f"/api/v1/tasks/{old['id']}").json()["status"] == "todo"


def test_submitted_past_due_is_not_backlog(auth_client):
    """昨天交了、家长没审——球在家长那边，不算孩子没完成。"""
    client, _ = auth_client
    yesterday = (local_today() - timedelta(days=1)).isoformat()
    task = create_task(client, task_date=yesterday)
    tid = task["id"]
    client.post(f"/api/v1/tasks/{tid}/start")
    client.post(f"/api/v1/tasks/{tid}/submit", json={"note": "ok"})

    assert tid in [t["id"] for t in client.get("/api/v1/tasks?bucket=review").json()]
    assert tid not in [t["id"] for t in client.get("/api/v1/tasks?bucket=backlog").json()]


def test_patch_only_when_todo(auth_client):
    client, _ = auth_client
    task = create_task(client)
    tid = task["id"]

    r = client.patch(f"/api/v1/tasks/{tid}", json={"stars": 5})
    assert r.status_code == 200
    assert r.json()["stars"] == 5
    assert r.json()["title"] == "口算 20 题"    # 没传的字段不动

    client.post(f"/api/v1/tasks/{tid}/start")
    assert client.patch(f"/api/v1/tasks/{tid}", json={"stars": 6}).status_code == 409
