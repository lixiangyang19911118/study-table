"""错题本：间隔重复的唯一入口。

节奏固定 1 / 2 / 4 / 7 天，连对 4 次算掌握：

    stage 0  刚录入，明天第 1 次复习
    stage 1  第 1 次对了，2 天后第 2 次
    stage 2  第 2 次对了，4 天后第 3 次
    stage 3  第 3 次对了，7 天后第 4 次
    stage 4  第 4 次也对了 → mastered，due_date 置空

任何一次答错都回到 stage 0、明天重来。这条规则看着粗暴，但它保证了
「没真会的题一定会再来」，不会因为前面答对几次就放过。

**判定人不是孩子**：对错由家长在审核任务时顺手判（见 tasks 的 approve），
孩子端只是做题、拍照、提交。错题不像口算那样能机器判分——
题干是照片、答案是手写，M3 不做 OCR。

计时的基准始终是 local_today()，不是 due_date：错题逾期三天才做，
下一次复习应该从今天开始算，而不是从原定的到期日。
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import local_today
from app.models import Mistake, MistakeLog, Task
from app.models.base import utcnow

# 每次答对后，距离下一次复习的天数。索引就是新的 stage。
INTERVAL_DAYS = (1, 2, 4, 7)
MASTER_STAGE = len(INTERVAL_DAYS)          # 4：连对 4 次

CATEGORIES = ("learning", "due", "mastered")
CAUSES = ("计算错", "看错题", "概念不清", "不会做")


class MistakeError(Exception):
    """错题操作被拒绝。路由层转 400/409。"""

    def __init__(self, message: str, code: str = "invalid_mistake", status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _log(db: Session, mistake_id: int, action: str, *,
         is_correct: bool | None = None, answer: str | None = None) -> None:
    db.add(MistakeLog(mistake_id=mistake_id, action=action,
                      is_correct=is_correct, answer=answer))


def _next_due(from_day: date, stage: int) -> date:
    """下一次复习日。stage 已经 +1，所以取 INTERVAL_DAYS[stage]。"""
    return from_day + timedelta(days=INTERVAL_DAYS[min(stage, MASTER_STAGE - 1)])


# ---------------------------------------------------------------- 录入


def create(
    db: Session,
    child_id: int,
    *,
    subject: str = "数学",
    point: str = "",
    stem: str = "",
    answer_own: str | None = None,
    answer_right: str | None = None,
    cause: str | None = None,
    file_id: int | None = None,
    source: str = "manual",
) -> Mistake:
    """录入一道错题。题干和照片至少要有一个，否则这条错题以后没法复习。"""
    stem = (stem or "").strip()
    if not stem and not file_id:
        raise MistakeError("题干和照片至少要有一个", code="empty_mistake")

    today = local_today()
    m = Mistake(
        child_id=child_id,
        subject=subject,
        point=(point or "").strip(),
        stem=stem,
        answer_own=answer_own,
        answer_right=answer_right,
        cause=cause,
        file_id=file_id,
        source=source,
        stage=0,
        due_date=today + timedelta(days=INTERVAL_DAYS[0]),
        mastered=False,
    )
    db.add(m)
    db.flush()                 # 拿到 id 才能写流水
    _log(db, m.id, "add", answer=answer_own)
    db.commit()
    db.refresh(m)
    return m


def update_fields(db: Session, m: Mistake, values: dict) -> Mistake:
    """改错因、知识点、正确答案。改题干要连照片一起看，留给前端做。"""
    for field, value in values.items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return m


# ---------------------------------------------------------------- 复习推进


def review(db: Session, m: Mistake, correct: bool, answer: str | None = None) -> Mistake:
    """记录一次复习结果，并排下一次。

    对了：stage + 1，按间隔表往后排；到 4 就掌握。
    错了：stage 归零，明天重来。

    这是全模块唯一会改 stage / due_date / mastered 的地方。
    家长在审核页判「做对了 / 还是错」，最终都落到这个函数。
    """
    if m.mastered:
        raise MistakeError("这道题已经标记掌握了，先重新打开再复习", code="already_mastered")
    if m.deleted_at is not None:
        raise MistakeError("这道题已被删除", code="deleted")

    today = local_today()
    if correct:
        m.stage = min(m.stage + 1, MASTER_STAGE)
        if m.stage >= MASTER_STAGE:
            m.mastered = True
            m.due_date = None
        else:
            m.due_date = _next_due(today, m.stage)
    else:
        # 回到起点。不用「stage - 1」是因为退一格并不能反映「这题其实没会」，
        # 实测中退一格会让错题在 4 次机会里蒙混过关。
        m.stage = 0
        m.due_date = today + timedelta(days=INTERVAL_DAYS[0])

    m.updated_at = utcnow()
    _log(db, m.id, "redo", is_correct=correct, answer=answer)
    db.commit()
    db.refresh(m)
    return m


def mark_mastered(db: Session, m: Mistake) -> Mistake:
    """手动标记掌握。孩子当场讲明白了、或这题本身出错了，不必走完 4 轮。"""
    m.mastered = True
    m.stage = MASTER_STAGE
    m.due_date = None
    m.updated_at = utcnow()
    _log(db, m.id, "master")
    db.commit()
    db.refresh(m)
    return m


def reopen(db: Session, m: Mistake) -> Mistake:
    """从已掌握恢复。标记错了、或孩子又忘了，重新进复习队列。"""
    m.mastered = False
    m.stage = 0
    m.due_date = local_today() + timedelta(days=INTERVAL_DAYS[0])
    m.updated_at = utcnow()
    _log(db, m.id, "reopen")
    db.commit()
    db.refresh(m)
    return m


def soft_delete(db: Session, m: Mistake) -> None:
    m.deleted_at = utcnow()
    db.commit()


# ---------------------------------------------------------------- 查询


def list_mistakes(
    db: Session, child_id: int, *, subject: str | None = None, category: str = "learning",
) -> list[Mistake]:
    """category 的三种口径：
    - learning  还没掌握的（含今天该复习的）
    - due       今天（或更早）该复习的
    - mastered  已掌握
    """
    today = local_today()
    stmt = select(Mistake).where(
        Mistake.child_id == child_id, Mistake.deleted_at.is_(None)
    )
    if category == "learning":
        stmt = stmt.where(Mistake.mastered.is_(False))
    elif category == "due":
        stmt = stmt.where(
            Mistake.mastered.is_(False),
            Mistake.due_date.is_not(None),
            Mistake.due_date <= today,
        )
    elif category == "mastered":
        stmt = stmt.where(Mistake.mastered.is_(True))
    else:
        raise ValueError(f"未知的 category：{category}")

    if subject:
        stmt = stmt.where(Mistake.subject == subject)
    # 到期的排前面：家长打开错题本最想看的就是「今天该复习哪些」
    return list(db.scalars(stmt.order_by(Mistake.due_date.is_(None), Mistake.due_date, Mistake.id)))


def logs(db: Session, mistake_id: int) -> list[MistakeLog]:
    return list(
        db.scalars(
            select(MistakeLog).where(MistakeLog.mistake_id == mistake_id).order_by(MistakeLog.id)
        )
    )


def from_task(db: Session, task: Task) -> Mistake | None:
    """从「错题重做」任务反查错题。任务不是错题来的、或错题已删，都返回 None。

    source_ref 的格式由 tasks/jobs.py 的扫描器写入，固定是 `mistake:<id>`。
    """
    ref = task.source_ref or ""
    if task.source != "mistake" or not ref.startswith("mistake:"):
        return None
    try:
        mistake_id = int(ref.split(":", 1)[1])
    except (IndexError, ValueError):
        return None
    return db.get(Mistake, mistake_id)


def counts(db: Session, child_id: int) -> dict[str, int]:
    """家长端仪表盘用的三个数。一次查出，不逐条 count。"""
    today = local_today()
    rows = list(
        db.scalars(
            select(Mistake).where(Mistake.child_id == child_id, Mistake.deleted_at.is_(None))
        )
    )
    learning = [m for m in rows if not m.mastered]
    return {
        "learning": len(learning),
        "due": len([m for m in learning if m.due_date is not None and m.due_date <= today]),
        "mastered": len([m for m in rows if m.mastered]),
    }
