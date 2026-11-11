"""星星余额与流水。

余额不是字段，是 `star_ledger.delta` 的聚合，所以这里没有任何写余额的代码，
只有「读聚合」和「追加流水」两种动作。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import default_child, get_current_account
from app.core.db import get_db
from app.models import Account
from app.schemas.star import AdjustIn, LedgerOut, StarsOut
from app.services import star_service as svc

router = APIRouter(tags=["星星"])


def _snapshot(db: Session, child_id: int, limit: int = 30, offset: int = 0) -> StarsOut:
    return StarsOut(
        balance=svc.balance(db, child_id),
        available=svc.available(db, child_id),
        pending=svc.pending_cost(db, child_id),
        ledger=[
            LedgerOut(
                id=e.id, delta=e.delta, reason=e.reason,
                ref_type=e.ref_type, created_at=e.created_at,
            )
            for e in svc.list_ledger(db, child_id, limit, offset)
        ],
    )


@router.get("/stars", response_model=StarsOut, summary="余额与流水")
def get_stars(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = default_child(account, db)
    return _snapshot(db, child.id, limit, offset)


@router.post("/stars/adjust", response_model=StarsOut, summary="家长手动加减星星")
def adjust_stars(
    body: AdjustIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """补发或扣罚。返回调整后的完整状态，前端不用再查一次。"""
    child = default_child(account, db)
    svc.adjust(db, child.id, body.delta, body.reason)
    return _snapshot(db, child.id)
