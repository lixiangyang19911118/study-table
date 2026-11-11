"""周报。全部实时聚合，库里没有周报表。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import default_child, get_current_account
from app.core.db import get_db
from app.models import Account
from app.schemas.report import WeeklyOut
from app.services import report_service

router = APIRouter(tags=["周报"])


@router.get("/reports/weekly", response_model=WeeklyOut, summary="某一周的汇总")
def weekly(
    week: str | None = Query(None, description="如 2026-W45，不传为本周"),
    account: Account = Depends(get_current_account),
    db: Session = Depends(get_db),
):
    child = default_child(account, db)
    try:
        return report_service.weekly(db, child.id, week)
    except ValueError as e:
        raise HTTPException(422, str(e))
