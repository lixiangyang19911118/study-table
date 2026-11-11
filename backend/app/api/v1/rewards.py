"""奖励清单与兑换。

兑换是两步：孩子 `POST /rewards/{id}/redeem` 落一条 pending，
家长 `POST /redemptions/{id}/approve` 才真的扣星。
中间这一步是刻意的——「看动画片 20 分钟」这类奖励本来就该家长点头，
孩子一点就把星扣光，等于家长被迫认账。
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import (
    default_child, get_current_account, owned_redemption, owned_reward,
)
from app.core.db import get_db
from app.models import Account, Reward, RewardRedemption
from app.schemas.reward import (
    DecideIn, RedeemIn, RedemptionOut, RewardIn, RewardOut, RewardPatch,
)
from app.services import star_service as svc

router = APIRouter(tags=["奖励与兑换"])


def _out(r: Reward, usable: int) -> RewardOut:
    return RewardOut(
        id=r.id, name=r.name, cost=r.cost, status=r.status,
        affordable=r.cost <= usable,
    )


def _redeem_out(r: RewardRedemption) -> RedemptionOut:
    return RedemptionOut(
        id=r.id, reward_id=r.reward_id, reward_name=r.reward_name,
        cost=r.cost, status=r.status, note=r.note,
        decided_at=r.decided_at, created_at=r.created_at,
    )


# ---------------------------------------------------------------- 奖励清单

@router.get("/rewards", response_model=list[RewardOut], summary="奖励清单")
def list_rewards(
    status: str | None = Query(None, pattern="^(on|off)$"),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = default_child(account, db)
    stmt = select(Reward).where(Reward.child_id == child.id)
    if status:
        stmt = stmt.where(Reward.status == status)
    usable = svc.available(db, child.id)
    return [_out(r, usable) for r in db.scalars(stmt.order_by(Reward.cost, Reward.id))]


@router.post("/rewards", response_model=RewardOut, summary="新增奖励")
def create_reward(
    body: RewardIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = default_child(account, db)
    r = Reward(child_id=child.id, name=body.name.strip(), cost=body.cost)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _out(r, svc.available(db, child.id))


@router.patch("/rewards/{reward_id}", response_model=RewardOut, summary="改名称/价格/上下架")
def patch_reward(
    reward_id: int,
    body: RewardPatch,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """改动不影响历史兑换：那笔记录的 name 与 cost 是快照。"""
    r = owned_reward(reward_id, account, db)
    data = body.model_dump(exclude_unset=True)
    if "name" in data:
        r.name = data["name"].strip()
    if "cost" in data:
        r.cost = data["cost"]
    if "status" in data:
        r.status = data["status"]
    db.commit()
    db.refresh(r)
    return _out(r, svc.available(db, r.child_id))


@router.delete("/rewards/{reward_id}", status_code=204, summary="删除奖励")
def delete_reward(
    reward_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """真的删。待确认的兑换会因外键 SET NULL 失去关联，但名称与价格快照还在，
    历史账目不会断——所以这里不做软删。"""
    r = owned_reward(reward_id, account, db)
    db.delete(r)
    db.commit()


# ---------------------------------------------------------------- 兑换

@router.get("/redemptions", response_model=list[RedemptionOut], summary="兑换记录")
def list_redemptions(
    status: str | None = Query(None, pattern="^(pending|approved|rejected|cancelled)$"),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = default_child(account, db)
    return [_redeem_out(r) for r in svc.list_redemptions(db, child.id, status)]


@router.post("/rewards/{reward_id}/redeem", response_model=RedemptionOut, summary="申请兑换")
def redeem(
    reward_id: int,
    body: RedeemIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """只落一条待确认记录，不动账。星星在家长批准那一刻才扣。"""
    reward = owned_reward(reward_id, account, db)
    return _redeem_out(svc.request_redeem(db, reward.child_id, reward, body.note))


@router.post("/redemptions/{redemption_id}/approve", response_model=RedemptionOut, summary="批准兑换")
def approve(
    redemption_id: int,
    body: DecideIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    row = owned_redemption(redemption_id, account, db)
    return _redeem_out(svc.approve(db, row, body.note))


@router.post("/redemptions/{redemption_id}/reject", response_model=RedemptionOut, summary="拒绝兑换")
def reject(
    redemption_id: int,
    body: DecideIn,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """拒绝必须写原因。孩子等来一个没有理由的「已拒绝」，比拒绝本身更难受。"""
    if not (body.note or "").strip():
        raise HTTPException(422, "请写一句原因，孩子才知道为什么不行")
    row = owned_redemption(redemption_id, account, db)
    return _redeem_out(svc.reject(db, row, body.note))


@router.post("/redemptions/{redemption_id}/cancel", response_model=RedemptionOut, summary="撤回申请")
def cancel(
    redemption_id: int,
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    row = owned_redemption(redemption_id, account, db)
    return _redeem_out(svc.cancel(db, row))
