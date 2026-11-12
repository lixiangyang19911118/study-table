"""听写：词表的清洗与归属规则。

这个模块没有状态机，也没有新表，风险全在「词表怎么洗」和「什么时候该拒」：

1. 去空行、去重、截断——家长从课文里复制粘贴，带空行和重复词是常态
2. `None` 与 `[]` 必须区别对待：普通任务没有词表是正常的，听写任务没有要报错
3. 非听写任务传了词表不该落库，否则将来统计要挨个判 kind
4. 听写任务的词表不能被改成空，否则孩子打开只剩一个空播放器
"""
from app.core.db import SessionLocal
from app.models import Task

PREFIX = "/api/v1"


def _create(c, **body) -> dict:
    r = c.post(f"{PREFIX}/tasks", json=body)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _detail(c, task_id: int) -> dict:
    r = c.get(f"{PREFIX}/tasks/{task_id}")
    assert r.status_code == 200, r.text
    return r.json()


def _dictation(c, words, **extra) -> dict:
    return _create(
        c, subject="语文", title="第 5 课生字听写", kind="dictation",
        words=words, minutes_est=15, stars=2, **extra,
    )


# ---------------------------------------------------------------- 词表清洗

def test_words_cleaned_on_create(auth_client):
    """空行、首尾空格、重复词都要在入库前处理掉。"""
    c, _ = auth_client
    task = _dictation(c, ["  苹果 ", "", "香蕉", "苹果", "   ", "橘子"])

    assert task["words"] == ["苹果", "香蕉", "橘子"]


def test_words_dedup_keeps_order(auth_client):
    """去重要保序：家长按课文顺序粘贴，顺序就是听写顺序。"""
    c, _ = auth_client
    task = _dictation(c, ["三", "一", "二", "一", "三"])
    assert task["words"] == ["三", "一", "二"]


def test_words_truncated_to_limit(auth_client):
    """超过 50 个只留前 50 个，不报错——家长多半是粘多了。"""
    c, _ = auth_client
    task = _dictation(c, [f"词{i}" for i in range(80)])

    assert len(task["words"]) == 50
    assert task["words"][0] == "词0"
    assert task["words"][-1] == "词49"


def test_word_length_capped(auth_client):
    """单条超过 32 字符截断，避免一行课文把播放器撑爆。"""
    c, _ = auth_client
    long_word = "很" * 50
    task = _dictation(c, [long_word])

    assert len(task["words"][0]) == 32


# ---------------------------------------------------------------- 拒绝的条件

def test_dictation_requires_words(auth_client):
    """听写任务没词表 → 400。孩子打开会是个空播放器。"""
    c, _ = auth_client
    for words in (None, [], ["", "  ", "\n"]):
        r = c.post(
            f"{PREFIX}/tasks",
            json={
                "subject": "语文", "title": "听写", "kind": "dictation",
                "words": words, "minutes_est": 10, "stars": 1,
            },
        )
        assert r.status_code == 400, f"{words!r} → {r.status_code}"
        assert "词表" in r.json()["detail"]


def test_normal_task_ignores_words(auth_client):
    """普通任务传了词表也不落库，别留下永远读不到的数据。"""
    c, info = auth_client
    task = _create(
        c, subject="语文", title="抄写第 5 课", kind="normal",
        words=["苹果", "香蕉"], minutes_est=20, stars=1,
    )

    assert task["words"] is None
    with SessionLocal() as db:
        row = db.get(Task, task["id"])
        assert row.words is None


def test_normal_task_without_words_ok(auth_client):
    """`None` 和 `[]` 的区别就在这里：普通任务压根可以不提词表。"""
    c, _ = auth_client
    task = _create(c, subject="数学", title="口算 20 题", kind="normal")
    assert task["words"] is None


# ---------------------------------------------------------------- 修改

def test_patch_words(auth_client):
    """待做的任务可以改词表，改完前端拿到的是洗过的结果。"""
    c, _ = auth_client
    task = _dictation(c, ["苹果", "香蕉"])

    r = c.patch(f"{PREFIX}/tasks/{task['id']}", json={"words": ["橘子", " 橘子 ", ""]})
    assert r.status_code == 200, r.text
    assert r.json()["words"] == ["橘子"]


def test_patch_words_to_empty_rejected(auth_client):
    """听写任务的词表不能清空。"""
    c, _ = auth_client
    task = _dictation(c, ["苹果"])

    r = c.patch(f"{PREFIX}/tasks/{task['id']}", json={"words": []})
    assert r.status_code == 400, r.text
    assert _detail(c, task["id"])["words"] == ["苹果"]


def test_patch_other_field_keeps_words(auth_client):
    """只改标题时不能把词表冲掉。"""
    c, _ = auth_client
    task = _dictation(c, ["苹果", "香蕉"])

    r = c.patch(f"{PREFIX}/tasks/{task['id']}", json={"title": "改个名字"})
    assert r.status_code == 200, r.text
    assert r.json()["words"] == ["苹果", "香蕉"]


# ---------------------------------------------------------------- 列表与详情

def test_words_in_list_and_detail(auth_client):
    """列表页要判断显示「听写」标签，详情页要拿去渲染播放器。"""
    c, _ = auth_client
    task = _dictation(c, ["苹果", "香蕉"])

    detail = _detail(c, task["id"])
    assert detail["kind"] == "dictation"
    assert detail["words"] == ["苹果", "香蕉"]

    r = c.get(f"{PREFIX}/tasks", params={"bucket": "today"})
    assert r.status_code == 200, r.text
    row = next(t for t in r.json() if t["id"] == task["id"])
    assert row["words"] == ["苹果", "香蕉"]


def test_dictation_task_runs_through_state_machine(auth_client):
    """听写复用普通任务的状态机，不额外开一条边。"""
    c, _ = auth_client
    task = _dictation(c, ["苹果"])

    assert c.post(f"{PREFIX}/tasks/{task['id']}/start").status_code == 200
    # 照片和说明都没有，服务层拒绝（不传 body 时走服务校验，返回 400）
    assert c.post(f"{PREFIX}/tasks/{task['id']}/submit").status_code == 400
    r = c.post(f"{PREFIX}/tasks/{task['id']}/submit", json={"note": "写完了"})
    assert r.status_code == 200, r.text
    assert c.post(f"{PREFIX}/tasks/{task['id']}/approve").json()["status"] == "done"
