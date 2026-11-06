"""任务主链路：布置 → 开始 → 提交 → 审核发星。

这里只做三件事：取参（哪个孩子 / 哪个任务）、调服务、把 ORM 拍成响应。
状态判断、计时结算、流水写入全在 services/task_service.py，
不要在路由里直接改 task.status。
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import default_child, get_current_account, owned_child, owned_task
from app.core.clock import local_today
from app.core.db import get_db
from app.models import Account, FileObject, Task, TaskReview, TaskShot
from app.schemas.task import (
    RejectIn, ShotIn, SubmitIn, TaskBrief, TaskCreate, TaskDetail, TaskPatch,
)
from app.services import task_service as svc

router = APIRouter(tags=["任务"])


def _brief(task: Task, shot_count: int) -> dict:
    return {
        "id": task.id,
        "subject": task.subject,
        "title": task.title,
        "kind": task.kind,
        "minutes_est": task.minutes_est,
        "stars": task.stars,
        "status": task.status,
        "source": task.source,
        "task_date": task.task_date,
        "spent_sec": task.spent_sec,
        "note": task.note,
        "submit_note": task.submit_note,
        "started_at": task.started_at,
        "submitted_at": task.submitted_at,
        "reviewed_at": task.reviewed_at,
        "shot_count": shot_count,
    }


def _detail(db: Session, task: Task) -> dict:
    shots = list(
        db.scalars(select(TaskShot).where(TaskShot.task_id == task.id).order_by(TaskShot.id))
    )
    reviews = list(
        db.scalars(select(TaskReview).where(TaskReview.task_id == task.id).order_by(TaskReview.id))
    )
    data = _brief(task, len(shots))
    data["shots"] = [
        {
            "id": s.id,
            "file_id": s.file_id,
            "url": f"/api/v1/files/{s.file_id}",
            "width": s.width,
            "height": s.height,
        }
        for s in shots
    ]
    data["reviews"] = [
        {"id": r.id, "action": r.action, "comment": r.comment, "created_at": r.created_at}
        for r in reviews
    ]
    return data


# ---------------------------------------------------------------- 增删改查


@router.post("/tasks", response_model=TaskDetail, status_code=201, summary="布置任务")
def create(
    body: TaskCreate,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = (
        owned_child(body.child_id, account, db) if body.child_id
        else default_child(account, db)
    )
    task = Task(
        child_id=child.id,
        subject=body.subject,
        title=body.title,
        kind=body.kind,
        minutes_est=body.minutes_est,
        stars=body.stars,
        note=body.note,
        task_date=body.task_date or local_today(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _detail(db, task)


@router.get("/tasks", response_model=list[TaskBrief], summary="任务列表（按桶）")
def index(
    bucket: str = Query("today", description="today 今日 / backlog 补做 / review 待审核 / done 已完成 / all"),
    day: date | None = Query(None, alias="date", description="不传则是今天"),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    if bucket not in svc.BUCKETS:
        raise HTTPException(400, f"bucket 只能是 {list(svc.BUCKETS)}")
    child = default_child(account, db)
    tasks = svc.list_tasks(db, child.id, bucket, day)
    counts = svc.shot_counts(db, [t.id for t in tasks])
    return [_brief(t, counts.get(t.id, 0)) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskDetail, summary="任务详情")
def show(
    task_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _detail(db, owned_task(task_id, account, db))


@router.patch("/tasks/{task_id}", response_model=TaskDetail, summary="修改任务（仅待做）")
def update(
    task_id: int,
    body: TaskPatch,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    task = owned_task(task_id, account, db)
    svc.update_fields(db, task, body.model_dump(exclude_unset=True, exclude_none=True))
    return _detail(db, task)


@router.delete("/tasks/{task_id}", status_code=204, summary="软删除任务")
def destroy(
    task_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    svc.soft_delete(db, owned_task(task_id, account, db))


# ---------------------------------------------------------------- 状态迁移


@router.post("/tasks/{task_id}/start", response_model=TaskDetail, summary="开始做")
def start(
    task_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _detail(db, svc.start(db, owned_task(task_id, account, db)))


@router.post("/tasks/{task_id}/restart", response_model=TaskDetail, summary="退回后重做")
def restart(
    task_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _detail(db, svc.restart(db, owned_task(task_id, account, db)))


@router.post("/tasks/{task_id}/submit", response_model=TaskDetail, summary="提交作业")
def submit(
    task_id: int,
    body: SubmitIn | None = None,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    note = body.note if body else None
    return _detail(db, svc.submit(db, owned_task(task_id, account, db), note))


@router.post("/tasks/{task_id}/withdraw", response_model=TaskDetail, summary="撤回提交")
def withdraw(
    task_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _detail(db, svc.withdraw(db, owned_task(task_id, account, db)))


@router.post("/tasks/{task_id}/approve", response_model=TaskDetail, summary="审核通过并发星")
def approve(
    task_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _detail(db, svc.approve(db, owned_task(task_id, account, db), account.id))


@router.post("/tasks/{task_id}/reject", response_model=TaskDetail, summary="退回重做")
def reject(
    task_id: int,
    body: RejectIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    task = owned_task(task_id, account, db)
    return _detail(db, svc.reject(db, task, account.id, body.comment))


# ---------------------------------------------------------------- 作业照片


@router.post("/tasks/{task_id}/shots", response_model=TaskDetail, status_code=201, summary="挂一张作业照片")
def add_shot(
    task_id: int,
    body: ShotIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    task = owned_task(task_id, account, db)
    obj = db.get(FileObject, body.file_id)
    if obj is None:
        raise HTTPException(404, "文件不存在")
    # 文件和孩子都要对上，否则挂一个别人家的 file_id 就能读到别人家的照片
    if obj.child_id != task.child_id:
        raise HTTPException(403, "这个文件不属于该任务的孩子")
    if obj.biz_type != "shot":
        raise HTTPException(400, "只有作业照片（biz_type=shot）能挂到任务上")
    svc.add_shot(db, task, obj.id, body.width, body.height)
    return _detail(db, task)


@router.delete("/tasks/{task_id}/shots/{shot_id}", response_model=TaskDetail, summary="删一张作业照片")
def remove_shot(
    task_id: int,
    shot_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    task = owned_task(task_id, account, db)
    shot = db.get(TaskShot, shot_id)
    if shot is None or shot.task_id != task.id:
        raise HTTPException(404, "照片不存在")
    svc.remove_shot(db, task, shot)
    return _detail(db, task)
