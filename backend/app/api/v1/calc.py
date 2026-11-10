"""口算接口。

三个约束，改的时候别破坏：
1. 出题响应里**没有答案**，答案只存在 calc_record.questions。
2. 判分只在 POST /rounds/{id}/submit 里发生，不接受前端传来的 right_count。
3. 交卷后如果这一轮挂在任务上，任务直接进 done 并发星（跳过待审核），
   星星按正确率折算，可能是 0——0 星时不写流水。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import default_child, get_current_account, owned_child, owned_task
from app.core.db import get_db
from app.models import Account, CalcRecord, Task
from app.schemas.calc import (
    CalcGenerateIn, CalcResultOut, CalcSubmitIn, RoundBrief, RoundOut, ToMistakesIn,
)
from app.services import calc_service
from app.services import task_service as task_svc

router = APIRouter(tags=["口算"])


def _owned_round(round_id: int, account: Account, db: Session) -> CalcRecord:
    rec = db.get(CalcRecord, round_id)
    if rec is None:
        raise HTTPException(404, "这一轮口算不存在")
    owned_child(rec.child_id, account, db)
    return rec


def _round_out(rec: CalcRecord) -> dict:
    """出题响应。逐题只给 index / type / stem，answer 永远不出库。"""
    return {
        "id": rec.id,
        "child_id": rec.child_id,
        "task_id": rec.task_id,
        "status": rec.status,
        "total": rec.total,
        "range_max": rec.range_max,
        "types": rec.types or [],
        "questions": [
            {"index": i, "type": q.get("type"), "stem": q.get("stem")}
            for i, q in enumerate(rec.questions or [])
        ],
    }


def _task_brief(task: Task) -> dict:
    return {
        "id": task.id, "subject": task.subject, "title": task.title, "kind": task.kind,
        "minutes_est": task.minutes_est, "stars": task.stars, "status": task.status,
        "source": task.source, "task_date": task.task_date, "spent_sec": task.spent_sec,
        "note": task.note, "submit_note": task.submit_note,
        "started_at": task.started_at, "submitted_at": task.submitted_at,
        "reviewed_at": task.reviewed_at, "shot_count": 0,
    }


# ---------------------------------------------------------------- 出题


@router.post("/calc/rounds", response_model=RoundOut, status_code=201, summary="出一套口算题")
def create_round(
    body: CalcGenerateIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = (
        owned_child(body.child_id, account, db) if body.child_id is not None
        else default_child(account, db)
    )

    if body.task_id is not None:
        task = owned_task(body.task_id, account, db)
        if task.child_id != child.id:
            raise HTTPException(400, "任务不属于这个孩子")
        if task.kind != "calc":
            raise HTTPException(400, "只有口算任务（kind=calc）能出题")
        if task.status == "todo":
            # 孩子从列表点进来直接做题，没手动点「开始」。
            # 这里补一次 start，否则交卷时任务不在 doing，结算会失败。
            task_svc.start(db, task)
        elif task.status != "doing":
            raise HTTPException(409, "这个任务不是进行中，不能出题")

    try:
        rec = calc_service.generate(
            db, child.id,
            count=body.count, range_max=body.range_max,
            types=body.types, task_id=body.task_id,
        )
    except calc_service.CalcError as e:
        raise HTTPException(e.status_code, str(e))

    return _round_out(rec)


# ---------------------------------------------------------------- 交卷


@router.post("/calc/rounds/{round_id}/submit", response_model=CalcResultOut, summary="交卷判分")
def submit(
    round_id: int,
    body: CalcSubmitIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    rec = _owned_round(round_id, account, db)
    try:
        rec = calc_service.submit(db, rec, body.answers, seconds=body.seconds)
    except calc_service.CalcError as e:
        raise HTTPException(e.status_code, str(e))

    # 只有挂在任务上的一轮才发星。独立练习只记 calc_record：
    # 否则孩子可以把同一个口算反复练到星星通胀。
    task_out = None
    earned = 0
    if rec.task_id is not None:
        task = db.get(Task, rec.task_id)
        if task is not None and task.deleted_at is None:
            if task.status == "doing":
                earned = calc_service.earned_stars(task.stars, rec)
                task = task_svc.complete_by_machine(db, task, earned, reason="口算完成")
            else:
                # 任务被别的路径改过状态（家长退回、任务被删）。
                # 不阻断交卷：孩子做完了就该看到分数，只是不再结算星星。
                earned = 0
            task_out = _task_brief(task)

    return {
        "id": rec.id,
        "total": rec.total,
        "right_count": rec.right_count,
        "seconds": rec.seconds,
        "accuracy": round(calc_service.accuracy(rec), 4),
        "stars_earned": earned,
        "task": task_out,
        "wrong": calc_service.wrong_items(rec),
    }


# ---------------------------------------------------------------- 错题入库


@router.post("/calc/rounds/{round_id}/to-mistakes", summary="把本轮错题加入错题本")
def to_mistakes(
    round_id: int,
    body: ToMistakesIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    rec = _owned_round(round_id, account, db)
    if rec.status != "done":
        raise HTTPException(409, "先交卷才能把错题加入错题本")
    created = calc_service.to_mistakes(db, rec, body.indexes)
    return {
        "created": len(created),
        "ids": [m.id for m in created],
        "first_due": created[0].due_date if created else None,
    }


# ---------------------------------------------------------------- 历史


@router.get("/calc/rounds", response_model=list[RoundBrief], summary="口算历史")
def list_rounds(
    limit: int = 20,
    child_id: int | None = None,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = owned_child(child_id, account, db) if child_id is not None else default_child(account, db)
    rows = calc_service.list_rounds(db, child.id, limit=max(1, min(limit, 100)))
    return [
        {
            "id": r.id, "created_at": r.created_at, "total": r.total,
            "right_count": r.right_count, "seconds": r.seconds,
            "range_max": r.range_max, "accuracy": round(calc_service.accuracy(r), 4),
        }
        for r in rows
    ]
