"""打卡日历。

只有两个动作：看日历、补记今天的打卡。孩子的「打卡」不是一个按钮——
当天任务全部完成才有资格，所以没有 POST /checkins（新建）这种接口，
免得孩子点一下就刷出一天连续。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import default_child, get_current_account
from app.core.clock import local_today
from app.core.db import get_db
from app.models import Account
from app.schemas.checkin import CalendarOut, SettleOut
from app.services import checkin_service as svc

router = APIRouter(tags=["打卡"])


@router.get("/checkins", response_model=CalendarOut, summary="打卡日历")
def get_calendar(
    month: str | None = Query(None, description="月份 2026-11，不传取本月"),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = default_child(account, db)
    return CalendarOut(**svc.calendar(db, child.id, month))


@router.post("/checkins/settle", response_model=SettleOut, summary="即时结算今天的打卡")
def settle(
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    """孩子做完最后一个任务时调一次，不必等到 23:55 的定时结算。

    幂等：当天已记过就返回 created=false，连着调十次也只会有一行。
    """
    child = default_child(account, db)
    created = svc.settle_today(db, child.id)
    days = svc.all_checked(db, child.id)
    today = local_today()
    return SettleOut(
        created=created,
        checked_today=today in days,
        streak=svc.streak(days, today),
    )
