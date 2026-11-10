"""错题本接口。

路由里只做三件事：解析归属（哪个孩子 / 哪道题）、调服务、把 ORM 拍成响应。
间隔推进、掌握、重新打开全在 services/mistake_service.py。

一条重要的边界：**这里没有「复习一次」的接口**。
错题的节奏只能由「家长审核错题重做任务」这一条路推进，
否则孩子在错题本里连点几次「我会了」，复习计划就被刷穿了。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import default_child, get_current_account, owned_child, owned_mistake
from app.core.db import get_db
from app.models import Account, FileObject, Mistake, MistakeLog
from app.schemas.mistake import (
    Category, MistakeBrief, MistakeCounts, MistakeCreate, MistakeDetail, MistakePatch,
)
from app.services import mistake_service as svc

router = APIRouter(tags=["错题"])


def _redo_counts(db: Session, mistake_ids: list[int]) -> dict[int, int]:
    """列表页一次查出复习次数，避免逐条 N+1。"""
    if not mistake_ids:
        return {}
    rows = db.execute(
        select(MistakeLog.mistake_id, func.count())
        .where(MistakeLog.mistake_id.in_(mistake_ids), MistakeLog.action == "redo")
        .group_by(MistakeLog.mistake_id)
    ).all()
    return {mid: n for mid, n in rows}


def _brief(m: Mistake, review_count: int) -> dict:
    return {
        "id": m.id,
        "subject": m.subject,
        "point": m.point,
        "stem": m.stem,
        "answer_own": m.answer_own,
        "answer_right": m.answer_right,
        "cause": m.cause,
        "source": m.source,
        "stage": m.stage,
        "due_date": m.due_date,
        "mastered": m.mastered,
        "file_url": f"/api/v1/files/{m.file_id}" if m.file_id else None,
        "review_count": review_count,
        "created_at": m.created_at,
    }


def _detail(db: Session, m: Mistake) -> dict:
    data = _brief(m, _redo_counts(db, [m.id]).get(m.id, 0))
    data["logs"] = [
        {
            "id": log.id,
            "action": log.action,
            "is_correct": log.is_correct,
            "answer": log.answer,
            "created_at": log.created_at,
        }
        for log in svc.logs(db, m.id)
    ]
    return data


# ---------------------------------------------------------------- 增删改查


@router.post("/mistakes", response_model=MistakeDetail, status_code=201, summary="录入错题")
def create(
    body: MistakeCreate,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = (
        owned_child(body.child_id, account, db) if body.child_id is not None
        else default_child(account, db)
    )
    # 照片归属要挡：挂一个别人家的 file_id 就能读到别人家孩子的作业
    if body.file_id is not None:
        obj = db.get(FileObject, body.file_id)
        if obj is None:
            raise HTTPException(404, "文件不存在")
        if obj.child_id != child.id:
            raise HTTPException(403, "这个文件不属于该孩子")
        if obj.biz_type != "mistake":
            raise HTTPException(400, "只有错题照片（biz_type=mistake）能挂到错题上")

    m = svc.create(
        db, child.id,
        subject=body.subject, point=body.point, stem=body.stem,
        answer_own=body.answer_own, answer_right=body.answer_right,
        cause=body.cause, file_id=body.file_id,
    )
    return _detail(db, m)


@router.get("/mistakes/counts", response_model=MistakeCounts, summary="错题三档计数")
def counts(
    child_id: int | None = Query(None),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """必须定义在 /mistakes/{mistake_id} 之前，否则 "counts" 会被当成 id。"""
    child = owned_child(child_id, account, db) if child_id is not None else default_child(account, db)
    return svc.counts(db, child.id)


@router.get("/mistakes", response_model=list[MistakeBrief], summary="错题列表")
def list_(
    category: Category = Query("learning", description="learning 未掌握 / due 今天该复习 / mastered 已掌握"),
    subject: str | None = Query(None),
    child_id: int | None = Query(None),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = owned_child(child_id, account, db) if child_id is not None else default_child(account, db)
    items = svc.list_mistakes(db, child.id, subject=subject, category=category)
    counts_ = _redo_counts(db, [m.id for m in items])
    return [_brief(m, counts_.get(m.id, 0)) for m in items]


@router.get("/mistakes/{mistake_id}", response_model=MistakeDetail, summary="错题详情")
def detail(
    mistake_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    return _detail(db, owned_mistake(mistake_id, account, db))


@router.patch("/mistakes/{mistake_id}", response_model=MistakeDetail, summary="改错题信息")
def patch(
    mistake_id: int,
    body: MistakePatch,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    m = owned_mistake(mistake_id, account, db)
    values = body.model_dump(exclude_unset=True, exclude_none=True)
    if not values:
        return _detail(db, m)
    return _detail(db, svc.update_fields(db, m, values))


@router.delete("/mistakes/{mistake_id}", status_code=204, summary="软删除错题")
def remove(
    mistake_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    svc.soft_delete(db, owned_mistake(mistake_id, account, db))


@router.post("/mistakes/{mistake_id}/master", response_model=MistakeDetail, summary="标记已掌握")
def master(
    mistake_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    m = owned_mistake(mistake_id, account, db)
    return _detail(db, svc.mark_mastered(db, m))


@router.post("/mistakes/{mistake_id}/reopen", response_model=MistakeDetail, summary="从已掌握恢复")
def reopen(
    mistake_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    m = owned_mistake(mistake_id, account, db)
    return _detail(db, svc.reopen(db, m))
