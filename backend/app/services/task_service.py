"""任务状态机。**所有 status 变更只能走这个模块**，路由层不许直接赋值。

理由：一次状态变更同时牵涉三件事——计时结算、审核流水、星星流水。
散在路由里迟早漏一处，最典型的就是「家长连点两下审核，孩子拿到两份星星」。

M2 定稿 5 态 6 边：

    todo      --start----->  doing       孩子开始做，记 started_at
    doing     --submit---->  submitted   照片或说明至少有一项
    submitted --approve--->  done        终态，写审核流水 + 星星流水
    submitted --reject---->  rejected    原因必填，清空 submit_note
    submitted --withdraw-->  doing       孩子撤回，started_at 重置避免重复计
    rejected  --restart--->  doing       重做，重新计时

`done` 没有出边：审核误点只能改库，不提供撤销接口（M2 明确不做）。

并发靠「带 status 条件的 UPDATE + 检查 rowcount」，不做先查后改。
两个请求同时进来时，只有一个能让 rowcount == 1，另一个拿 409。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.clock import local_today
from app.models import StarLedger, Task, TaskReview, TaskShot
from app.models.base import utcnow

STATUS_LABEL = {
    "todo": "待做",
    "doing": "进行中",
    "submitted": "待审核",
    "done": "已完成",
    "rejected": "已退回",
}

# 「还没交出去」的三个状态：可以改、可以加照片、可以删、逾期归入补做区
OPEN_STATUSES = ("todo", "doing", "rejected")
# 能加/删照片的状态：提交之后就锁住，要加先撤回
EDITABLE_SHOT_STATUSES = ("todo", "doing", "rejected")
BUCKETS = ("today", "backlog", "review", "done", "all")

# 单次计时上限。孩子开着页面去吃饭，回来一提交就是三小时，
# 不设上限会让「今日用时」彻底失去参考价值。
MAX_SPENT_SEC = 12 * 3600


class TaskStateError(Exception):
    """状态机拒绝这次操作。路由层统一转成 409/400，带 code 便于前端分辨。"""

    def __init__(self, message: str, code: str = "invalid_transition", status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _reject(task: Task, code: str = "invalid_transition", status_code: int = 409) -> TaskStateError:
    label = STATUS_LABEL.get(task.status, task.status)
    return TaskStateError(
        f"任务当前是「{label}」，不能执行这个操作", code=code, status_code=status_code
    )


def _transition(db: Session, task: Task, expect: tuple[str, ...], to_status: str, **values) -> None:
    """带前置状态的条件更新。不提交事务，由调用方和流水一起提交。"""
    now = utcnow()
    values.setdefault("updated_at", now)
    stmt = (
        update(Task)
        .where(Task.id == task.id, Task.status.in_(expect), Task.deleted_at.is_(None))
        .values(status=to_status, **values)
        .execution_options(synchronize_session=False)
    )
    if db.execute(stmt).rowcount == 0:
        db.rollback()
        db.refresh(task)          # 拿到真实状态再报错，提示词才不会指错方向
        raise _reject(task)


def _finish(db: Session, task: Task) -> Task:
    db.commit()
    db.refresh(task)
    return task


def _elapsed_sec(task: Task, now) -> int:
    """本段计时。started_at 为空（历史数据）就当 0。"""
    if task.started_at is None:
        return 0
    return max(0, min(int((now - task.started_at).total_seconds()), MAX_SPENT_SEC))


# ---------------------------------------------------------------- 状态迁移


def start(db: Session, task: Task) -> Task:
    """todo → doing。"""
    _transition(db, task, ("todo",), "doing", started_at=utcnow())
    return _finish(db, task)


def restart(db: Session, task: Task) -> Task:
    """rejected → doing。重做重新计时，不然「重做用了几分钟」永远是负数。"""
    _transition(db, task, ("rejected",), "doing", started_at=utcnow())
    return _finish(db, task)


def submit(db: Session, task: Task, note: str | None = None) -> Task:
    """doing → submitted。

    提交条件：至少 1 张照片，或写了一句说明——二选一即可。
    被退回过一次之后，还要求「这一轮有新东西」：新照片或新说明。
    否则退回毫无意义，孩子原样再点一次提交就绕过去了。
    """
    now = utcnow()
    # 先看状态再看内容：待做的任务该报「状态不对」，而不是「没交东西」，
    # 否则前端提示会把人往错的方向引。
    if task.status != "doing":
        raise _reject(task)

    note_text = (note or "").strip() or task.submit_note
    shots = db.scalar(
        select(func.count()).select_from(TaskShot).where(TaskShot.task_id == task.id)
    ) or 0

    last_reject = db.scalar(
        select(func.max(TaskReview.created_at)).where(
            TaskReview.task_id == task.id, TaskReview.action == "reject"
        )
    )
    if last_reject is not None:
        # 退回时 submit_note 已被清空，所以「有说明」就等于「新说明」
        fresh_shots = db.scalar(
            select(func.count())
            .select_from(TaskShot)
            .where(TaskShot.task_id == task.id, TaskShot.created_at > last_reject)
        ) or 0
        if fresh_shots == 0 and not note_text:
            raise TaskStateError(
                "退回后要重新提交，请至少补 1 张照片，或写一句改了什么",
                code="redo_nothing_new", status_code=400,
            )
    elif shots == 0 and not note_text:
        raise TaskStateError(
            "提交前请至少上传 1 张作业照片，或写一句说明", code="nothing_to_submit",
            status_code=400,
        )

    _transition(
        db, task, ("doing",), "submitted",
        submitted_at=now,
        submit_note=note_text,
        spent_sec=task.spent_sec + _elapsed_sec(task, now),
    )
    return _finish(db, task)


def withdraw(db: Session, task: Task) -> Task:
    """submitted → doing。孩子撤回提交，比如发现少拍了一页。

    started_at 重置为现在：已花的时长已经结算进 spent_sec，
    不重置的话下一次提交会把同一段时间再算一遍。
    """
    _transition(db, task, ("submitted",), "doing", started_at=utcnow())
    return _finish(db, task)


def approve(db: Session, task: Task, reviewer_id: int | None) -> Task:
    """submitted → done。条件更新与发星在同一个事务里，重复提交只成功一次。"""
    _transition(db, task, ("submitted",), "done", reviewed_at=utcnow())
    db.add(TaskReview(task_id=task.id, reviewer_id=reviewer_id, action="approve"))
    db.add(
        StarLedger(
            child_id=task.child_id,
            delta=task.stars,
            reason="完成任务",
            ref_type="task",
            ref_id=task.id,
        )
    )
    return _finish(db, task)


def reject(db: Session, task: Task, reviewer_id: int | None, comment: str | None) -> Task:
    """submitted → rejected。原因必填，且清空孩子上一轮的说明。"""
    text = (comment or "").strip()
    if not text:
        raise TaskStateError("退回时要写一句原因", code="comment_required", status_code=422)
    _transition(
        db, task, ("submitted",), "rejected",
        reviewed_at=utcnow(),
        submit_note=None,          # 上一轮说明随这次提交一起作废
    )
    db.add(
        TaskReview(task_id=task.id, reviewer_id=reviewer_id, action="reject", comment=text)
    )
    return _finish(db, task)


# ---------------------------------------------------------------- 照片与编辑


def add_shot(db: Session, task: Task, file_id: int, width: int | None, height: int | None) -> TaskShot:
    if task.status not in EDITABLE_SHOT_STATUSES:
        raise TaskStateError("已提交的任务不能再加照片，请先撤回提交", code="shots_locked")
    shot = TaskShot(task_id=task.id, file_id=file_id, width=width, height=height)
    db.add(shot)
    db.commit()
    db.refresh(shot)
    return shot


def remove_shot(db: Session, task: Task, shot: TaskShot) -> None:
    if task.status not in EDITABLE_SHOT_STATUSES:
        raise TaskStateError("已提交的任务不能删照片，请先撤回提交", code="shots_locked")
    # 只删引用，file_object 与磁盘文件留着：审核页可能正显示它，
    # 也方便排查「明明传过怎么没了」。
    db.delete(shot)
    db.commit()


def update_fields(db: Session, task: Task, values: dict) -> Task:
    """只有待做的任务能改。一旦开始做，改动会让已花的时间失去意义。"""
    if task.status != "todo":
        raise TaskStateError("只有还没开始的任务可以修改", code="not_editable")
    for field, value in values.items():
        setattr(task, field, value)
    return _finish(db, task)


def soft_delete(db: Session, task: Task) -> None:
    """软删除。已完成的不许删——周报和星星记录要能对上账。"""
    if task.status == "done":
        raise TaskStateError("已完成的任务不能删除", code="not_deletable")
    if task.status not in OPEN_STATUSES:
        raise TaskStateError("待审核的任务不能删除，请先退回或让孩子撤回", code="not_deletable")
    task.deleted_at = utcnow()
    db.commit()


# ---------------------------------------------------------------- 查询


def list_tasks(db: Session, child_id: int, bucket: str = "today", day: date | None = None) -> list[Task]:
    """bucket 决定「今日 / 补做 / 待审核 / 已完成」的口径。

    逾期不是一种状态，是算出来的：task_date 早于今天且还没交出去。
    好处是不依赖定时任务——电脑关机三天再打开，补做区依然是对的。
    """
    day = day or local_today()
    stmt = select(Task).where(Task.child_id == child_id, Task.deleted_at.is_(None))

    if bucket == "today":
        stmt = stmt.where(Task.task_date == day, Task.status.in_(OPEN_STATUSES))
        stmt = stmt.order_by(Task.id)
    elif bucket == "backlog":
        stmt = stmt.where(Task.task_date < day, Task.status.in_(OPEN_STATUSES))
        stmt = stmt.order_by(Task.task_date, Task.id)
    elif bucket == "review":
        # 跨天没审的任务仍然留在待审核：球在家长那边，不该算孩子没完成
        stmt = stmt.where(Task.status == "submitted").order_by(Task.submitted_at)
    elif bucket == "done":
        stmt = stmt.where(Task.status == "done", Task.task_date == day).order_by(Task.id)
    elif bucket != "all":
        raise ValueError(f"未知的 bucket：{bucket}")

    return list(db.scalars(stmt))


def shot_counts(db: Session, task_ids: list[int]) -> dict[int, int]:
    """列表页一次查出所有任务的照片数，避免逐条 N+1。"""
    if not task_ids:
        return {}
    rows = db.execute(
        select(TaskShot.task_id, func.count())
        .where(TaskShot.task_id.in_(task_ids))
        .group_by(TaskShot.task_id)
    ).all()
    return {task_id: count for task_id, count in rows}
