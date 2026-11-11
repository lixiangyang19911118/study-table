"""定时任务的具体动作。

两个原则：
1. 任务本身必须幂等，不依赖调度器只跑一次（详见 v1.1 缺口 2）。
2. 每个函数自己开关 Session，方便被 CLI 手动补跑。
"""
import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Mistake, Task
from app.services.checkin_service import settle_child

log = logging.getLogger(__name__)


def _today() -> date:
    return datetime.now(ZoneInfo(settings.TIMEZONE)).date()


def scan_due_mistakes() -> int:
    """把今天到期、未掌握的错题生成今日任务。返回新建条数。

    幂等靠 task 表唯一约束 uk_task_source 兜底：
    同一 (child_id, task_date, source_ref) 只会有一行。
    """
    today = _today()
    created = 0
    with SessionLocal() as db:
        due = db.scalars(
            select(Mistake).where(
                Mistake.mastered.is_(False),
                Mistake.deleted_at.is_(None),
                Mistake.due_date.is_not(None),
                Mistake.due_date <= today,
            )
        ).all()

        for m in due:
            ref = f"mistake:{m.id}"
            exists = db.scalar(
                select(Task.id).where(
                    Task.child_id == m.child_id,
                    Task.task_date == today,
                    Task.source_ref == ref,
                )
            )
            if exists:
                continue
            db.add(
                Task(
                    child_id=m.child_id,
                    subject=m.subject,
                    title=f"错题重做 · {m.point or m.subject}",
                    kind="redo",
                    source="mistake",
                    source_ref=ref,
                    task_date=today,
                    minutes_est=8,
                    stars=1,
                )
            )
            created += 1
        db.commit()

    log.info("错题到期扫描：生成 %s 条今日任务", created)
    return created


def settle_checkin() -> int:
    """当天任务全部完成则记一次打卡。返回新增打卡数。

    判定规则与 `POST /checkins/settle` 共用 checkin_service.settle_child，
    否则「什么算完成任务」会在两处慢慢漂。这里负责按孩子循环 + 统一提交。
    """
    today = _today()
    added = 0
    with SessionLocal() as db:
        child_ids = db.scalars(
            select(Task.child_id).where(
                Task.task_date == today, Task.deleted_at.is_(None)
            ).distinct()
        ).all()

        for child_id in child_ids:
            if settle_child(db, child_id, today):
                added += 1
        db.commit()

    log.info("打卡结算：新增 %s 条", added)
    return added
