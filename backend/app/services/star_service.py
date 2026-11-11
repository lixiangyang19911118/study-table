"""星星余额与兑换。

余额不存字段，是 `star_ledger.delta` 的 SUM。这个选择让每一颗星都能逐条核对，
但也带来两个必须正面处理的问题：

1. **「查余额 → 插负向流水」之间有窗口。**
   孩子连点两下兑换，两次都读到 100 颗、各扣 80，余额变 -60。
   解法：扣减前先 `SELECT ... FOR UPDATE` 锁住 child 行，把同一个孩子的
   兑换串行化。锁的是一行 child，兑换本身是低频操作，代价可以接受。

2. **pending 的申请必须占住余额。**
   否则孩子可以连提十笔 80 颗的申请，家长逐条批下去才发现透支。
   所以有了「可用余额」：`余额 - 所有 pending 的 cost 之和`。
   申请时按可用余额挡，批准时再按一次（期间可能又批了别的）。

批准才扣星是这个模块最核心的一条：pending 期间不动账，
孩子看到的是「申请已提交」，家长点确认才真的少星星。
"""
from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import BizError
from app.models import Child, Reward, RewardRedemption, StarLedger
from app.models.base import utcnow

MAX_ADJUST = 1000


class StarError(BizError):
    """星星操作被拒绝。"""

    def __init__(self, message: str, code: str = "invalid_stars", status_code: int = 400):
        super().__init__(message, code, status_code)


# ---------------------------------------------------------------- 账目口径

def balance(db: Session, child_id: int) -> int:
    """余额 = 所有流水之和。没有余额字段，所以永远不会和流水对不上。"""
    return int(
        db.scalar(
            select(func.coalesce(func.sum(StarLedger.delta), 0)).where(
                StarLedger.child_id == child_id
            )
        ) or 0
    )


def pending_cost(db: Session, child_id: int, exclude_id: int | None = None) -> int:
    """待确认的兑换一共占了多少颗星。

    exclude_id 用于「批准某一条时把它自己排除掉」——它自己的 cost
    还挂在 pending 里，不排除的话会把自己算成占用，永远差一颗。
    """
    stmt = select(func.coalesce(func.sum(RewardRedemption.cost), 0)).where(
        RewardRedemption.child_id == child_id,
        RewardRedemption.status == "pending",
    )
    if exclude_id is not None:
        stmt = stmt.where(RewardRedemption.id != exclude_id)
    return int(db.scalar(stmt) or 0)


def available(db: Session, child_id: int, exclude_id: int | None = None) -> int:
    """可用余额：能拿去兑换的星星。"""
    return balance(db, child_id) - pending_cost(db, child_id, exclude_id)


def _lock_child(db: Session, child_id: int) -> None:
    """锁住孩子行，把同一孩子的星星操作串行化。

    单行主键锁，不会有间隙锁的意外；兑换是低频操作，
    并发等一两毫秒远比透支后再改库便宜。
    """
    db.execute(select(Child.id).where(Child.id == child_id).with_for_update())


def _write(
    db: Session, child_id: int, delta: int, reason: str,
    ref_type: str | None = None, ref_id: int | None = None,
) -> StarLedger:
    entry = StarLedger(
        child_id=child_id, delta=delta, reason=reason,
        ref_type=ref_type, ref_id=ref_id,
    )
    db.add(entry)
    return entry


def list_ledger(db: Session, child_id: int, limit: int = 30, offset: int = 0) -> list[StarLedger]:
    return list(
        db.scalars(
            select(StarLedger)
            .where(StarLedger.child_id == child_id)
            .order_by(StarLedger.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


# ---------------------------------------------------------------- 家长补发

def adjust(db: Session, child_id: int, delta: int, reason: str | None = None) -> StarLedger:
    """家长手动加减星星。delta 为正是奖励，为负是扣罚。"""
    if delta == 0:
        raise StarError("变动值不能是 0", code="zero_delta")
    if abs(delta) > MAX_ADJUST:
        raise StarError(f"单次调整不能超过 {MAX_ADJUST} 颗", code="too_large")

    _lock_child(db, child_id)
    if delta < 0 and available(db, child_id) + delta < 0:
        # 扣罚要看可用余额：待确认的兑换已经把那部分星星占住了
        raise StarError(
            f"扣完会变成负数：可用 {available(db, child_id)} 颗，本次要扣 {abs(delta)} 颗",
            code="insufficient_stars",
        )

    entry = _write(db, child_id, delta, reason or "家长补发", ref_type="manual")
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------- 兑换

def request_redeem(db: Session, child_id: int, reward: Reward, note: str | None = None) -> RewardRedemption:
    """孩子发起兑换。只落一条 pending，不动账。"""
    if reward.status != "on":
        raise StarError("这个奖励已经下架了", code="reward_off")

    _lock_child(db, child_id)
    usable = available(db, child_id)
    if usable < reward.cost:
        raise StarError(
            f"星星还不够：可用 {usable} 颗，需要 {reward.cost} 颗",
            code="insufficient_stars",
        )

    row = RewardRedemption(
        child_id=child_id,
        reward_id=reward.id,
        reward_name=reward.name,   # 快照：改名或删掉都不影响这条历史
        cost=reward.cost,          # 快照：改价不影响这笔账
        status="pending",
        note=note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def approve(db: Session, redemption: RewardRedemption, note: str | None = None) -> RewardRedemption:
    """家长批准。这里才真正扣星。

    顺序是「先锁 → 再校验 → 再改状态 → 最后写流水」：
    校验放最前面，不通过时什么都没动过，不需要回滚。
    """
    if redemption.status != "pending":
        raise StarError("这笔兑换已经处理过了", code="already_decided", status_code=409)

    child_id = redemption.child_id
    _lock_child(db, child_id)

    # 期间可能又批了别的 pending，所以用「排除自己」的口径重算一次
    usable = available(db, child_id, exclude_id=redemption.id)
    if usable < redemption.cost:
        raise StarError(
            f"星星不够了：可用 {usable} 颗，这笔要 {redemption.cost} 颗",
            code="insufficient_stars",
        )

    res = db.execute(
        update(RewardRedemption)
        .where(
            RewardRedemption.id == redemption.id,
            RewardRedemption.status == "pending",
        )
        .values(status="approved", decided_at=utcnow(), note=note or redemption.note)
    )
    if res.rowcount == 0:
        # 两个设备同时点批准，只有一个能让 rowcount 变 1
        raise StarError("这笔兑换已经处理过了", code="already_decided", status_code=409)

    _write(
        db, child_id, -redemption.cost,
        # reason 是 varchar(32)，reward_name 最长 64 —— 不截断会在严格模式下
        # 直接报 Data too long，而且是在提交时才炸，极难定位
        f"兑换：{redemption.reward_name}"[:32],
        ref_type="redemption", ref_id=redemption.id,
    )
    db.commit()
    db.refresh(redemption)
    return redemption


def reject(db: Session, redemption: RewardRedemption, note: str) -> RewardRedemption:
    """家长拒绝。原因必填——孩子等了两天等来一个「已拒绝」，比拒绝本身更难受。"""
    if redemption.status != "pending":
        raise StarError("这笔兑换已经处理过了", code="already_decided", status_code=409)

    text = (note or "").strip()
    if not text:
        raise StarError("请写一句原因，孩子才知道为什么不行", code="note_required")

    res = db.execute(
        update(RewardRedemption)
        .where(
            RewardRedemption.id == redemption.id,
            RewardRedemption.status == "pending",
        )
        .values(status="rejected", decided_at=utcnow(), note=text[:255])
    )
    if res.rowcount == 0:
        raise StarError("这笔兑换已经处理过了", code="already_decided", status_code=409)

    db.commit()
    db.refresh(redemption)
    return redemption


def cancel(db: Session, redemption: RewardRedemption) -> RewardRedemption:
    """孩子撤回申请。只有待确认的能撤，已经批了的不行——那已经是一笔账了。"""
    if redemption.status != "pending":
        raise StarError("已经处理过的兑换不能撤回", code="already_decided", status_code=409)

    res = db.execute(
        update(RewardRedemption)
        .where(
            RewardRedemption.id == redemption.id,
            RewardRedemption.status == "pending",
        )
        .values(status="cancelled", decided_at=utcnow())
    )
    if res.rowcount == 0:
        raise StarError("这笔兑换已经处理过了", code="already_decided", status_code=409)

    db.commit()
    db.refresh(redemption)
    return redemption


def list_redemptions(
    db: Session, child_id: int, status: str | None = None, limit: int = 30,
) -> list[RewardRedemption]:
    stmt = select(RewardRedemption).where(RewardRedemption.child_id == child_id)
    if status:
        stmt = stmt.where(RewardRedemption.status == status)
    return list(db.scalars(stmt.order_by(RewardRedemption.id.desc()).limit(limit)))
