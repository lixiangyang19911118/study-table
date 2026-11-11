"""口算：出题与判分都在后端。

**为什么不能在前端判分**：前端判分意味着把答案随题目一起下发，孩子按 F12
就能看到全部答案；而且「答对几道」由前端自己算，改一下请求就能满分。
所以这里出题时答案只写进 calc_record.questions，响应里只给题干。

一轮的生命周期只有两步，对应 calc_record.status：

    出题  → status=doing，写 questions（含答案）、total、types
    交卷  → status=done，写 answers、right_count、seconds

判分是纯函数式的字符串比对，不做浮点比较、不做近似——小学口算的答案
都是整数，近似匹配只会让「答对了」变得不可信。

星星按正确率折算（M3 定稿）：实得 = ceil(任务星星 × 正确率)。
全对满星，对一半拿一半，全错拿 0。既不让孩子因为错一道就归零，
也不让全错也拿满星。
"""
from __future__ import annotations

import math
import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BizError
from app.models.base import utcnow
from app.models.entities import CalcRecord, Mistake

# 有明确语义差异的六种，作为默认出题组合。
# fill_sum / fill_diff 与 add / sub 同形（都是「结果位留空」），
# 只为兼容旧数据保留支持，默认不出——同一个 "3 + 5 = ?" 不该算两种题型。
DEFAULT_TYPES = ("add", "sub", "fill_addend", "fill_minuend", "chain_add", "chain_sub")
ALL_TYPES = DEFAULT_TYPES + ("fill_sum", "fill_diff")
RANGES = (10, 20, 100)

MAX_COUNT = 50
MIN_COUNT = 5
# 一轮用时的兜底上限。孩子开着页面出去玩，回来一交卷就是两小时，
# 不设上限会让「正确率与用时」这两个指标一起失真。
MAX_SECONDS = 30 * 60

# 全角数字与符号。孩子用中文输入法时很容易打出「１２」，要认。
_FULLWIDTH = str.maketrans(
    "０１２３４５６７８９－＋＝　", "0123456789-+= "
)


class CalcError(BizError):
    def __init__(self, message: str, code: str = "invalid_calc", status_code: int = 400):
        super().__init__(message, code, status_code)


# ---------------------------------------------------------------- 出题

def _q_add(rng: random.Random, m: int) -> tuple[str, int]:
    a = rng.randint(1, m - 1)
    b = rng.randint(1, m - a) if m - a >= 1 else 1
    return f"{a} + {b} = ?", a + b


def _q_sub(rng: random.Random, m: int) -> tuple[str, int]:
    a = rng.randint(2, m)
    b = rng.randint(1, a - 1)
    return f"{a} - {b} = ?", a - b


def _q_fill_addend(rng: random.Random, m: int) -> tuple[str, int]:
    """3 + ( ) = 8，求另一个加数。"""
    c = rng.randint(2, m)
    a = rng.randint(1, c - 1)
    return f"{a} + ( ) = {c}", c - a


def _q_fill_minuend(rng: random.Random, m: int) -> tuple[str, int]:
    """( ) - 3 = 5，求被减数。逆向思考，比求差难一档。"""
    a = rng.randint(2, m)
    b = rng.randint(1, a - 1)
    return f"( ) - {b} = {a - b}", a


def _q_fill_sum(rng: random.Random, m: int) -> tuple[str, int]:
    a = rng.randint(1, m - 1)
    b = rng.randint(1, max(1, m - a))
    return f"{a} + {b} = ( )", a + b


def _q_fill_diff(rng: random.Random, m: int) -> tuple[str, int]:
    a = rng.randint(2, m)
    b = rng.randint(1, a - 1)
    return f"{a} - {b} = ( )", a - b


def _q_chain_add(rng: random.Random, m: int) -> tuple[str, int]:
    """连加三个数，和不超过范围。"""
    cap = max(1, m // 4)
    a = rng.randint(1, cap)
    b = rng.randint(1, cap)
    rest = m - a - b
    c = rng.randint(1, rest) if rest >= 1 else 1
    return f"{a} + {b} + {c} = ?", a + b + c


def _q_chain_sub(rng: random.Random, m: int) -> tuple[str, int]:
    a = rng.randint(3, m)
    b = rng.randint(1, a - 2)
    c = rng.randint(1, a - b)
    return f"{a} - {b} - {c} = ?", a - b - c


_MAKERS = {
    "add": _q_add,
    "sub": _q_sub,
    "fill_addend": _q_fill_addend,
    "fill_minuend": _q_fill_minuend,
    "fill_sum": _q_fill_sum,
    "fill_diff": _q_fill_diff,
    "chain_add": _q_chain_add,
    "chain_sub": _q_chain_sub,
}


def generate(
    db: Session,
    child_id: int,
    *,
    count: int = 20,
    range_max: int = 20,
    types: list[str] | None = None,
    task_id: int | None = None,
    rng: random.Random | None = None,
) -> CalcRecord:
    """出一套题并存库。返回的 record 里有答案，调用方**不要**把它整个返回给前端。"""
    if not MIN_COUNT <= count <= MAX_COUNT:
        raise CalcError(f"每轮题数要在 {MIN_COUNT}-{MAX_COUNT} 之间", code="bad_count")
    if range_max not in RANGES:
        raise CalcError(f"数值范围只能是 {RANGES} 之一", code="bad_range")

    use_types = tuple(types or DEFAULT_TYPES)
    unknown = [t for t in use_types if t not in _MAKERS]
    if unknown:
        raise CalcError(f"未知题型：{unknown}", code="bad_type")

    rng = rng or random.Random()
    questions: list[dict] = []
    seen: set[str] = set()
    # 每道题最多试 20 次去重。范围 10 以内、20 道题时重复几乎必然发生，
    # 硬性要求不重复会死循环，所以试满就放过。
    for i in range(count):
        kind = use_types[i % len(use_types)]
        stem, answer = _MAKERS[kind](rng, range_max)
        for _ in range(20):
            if stem not in seen:
                break
            stem, answer = _MAKERS[kind](rng, range_max)
        seen.add(stem)
        questions.append({"type": kind, "stem": stem, "answer": str(answer)})

    rec = CalcRecord(
        child_id=child_id,
        task_id=task_id,
        range_max=range_max,
        total=count,
        right_count=0,
        seconds=0,
        status="doing",
        questions=questions,
        answers=None,
        types=list(use_types),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


# ---------------------------------------------------------------- 判分

def _normalize(raw: str | None) -> str:
    if raw is None:
        return ""
    return raw.translate(_FULLWIDTH).strip().replace(" ", "")


def _is_right(given: str | None, expected: str) -> bool:
    """先按整数比，退化到字符串比。空作答一律算错。"""
    g = _normalize(given)
    if not g:
        return False
    e = _normalize(expected)
    try:
        return int(g) == int(e)
    except ValueError:
        return g == e


def grade(rec: CalcRecord, answers: list[str | None]) -> None:
    """逐题比对，结果写回 record。**不提交事务**，由调用方和任务结算一起提交。"""
    questions = rec.questions or []
    given = list(answers) + [None] * max(0, len(questions) - len(answers))
    given = given[: len(questions)]

    right = sum(
        1 for q, a in zip(questions, given) if _is_right(a, str(q.get("answer", "")))
    )
    rec.answers = given
    rec.right_count = right
    rec.status = "done"


def submit(
    db: Session, rec: CalcRecord, answers: list[str | None], *, seconds: int | None = None
) -> CalcRecord:
    """交卷。用 status 条件更新挡重复交卷。"""
    if rec.status != "doing":
        raise CalcError("这一轮已经交过卷了", code="already_submitted", status_code=409)

    now = utcnow()
    elapsed = seconds
    if elapsed is None:
        elapsed = int((now - rec.created_at).total_seconds())
    rec.seconds = max(0, min(int(elapsed), MAX_SECONDS))
    rec.updated_at = now
    grade(rec, answers)

    # 条件更新兜住并发：两个标签页同时交卷，只有一个能把 doing 改成 done
    from sqlalchemy import update as _update

    result = db.execute(
        _update(CalcRecord)
        .where(CalcRecord.id == rec.id, CalcRecord.status == "doing")
        .values(
            status="done",
            answers=rec.answers,
            right_count=rec.right_count,
            seconds=rec.seconds,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        db.rollback()
        raise CalcError("这一轮已经交过卷了", code="already_submitted", status_code=409)

    db.commit()
    db.refresh(rec)
    return rec


# ---------------------------------------------------------------- 结算

def accuracy(rec: CalcRecord) -> float:
    return (rec.right_count / rec.total) if rec.total else 0.0


def earned_stars(task_stars: int, rec: CalcRecord) -> int:
    """按正确率折算星星，向上取整。

    ceil 而不是 floor：对 8 道（40%）给 1 颗而不是 0 颗，
    让孩子看到「做了 20 道」和「一颗没有」不至于同时成立。
    """
    if rec.total <= 0:
        return 0
    return int(math.ceil(task_stars * accuracy(rec)))


def wrong_items(rec: CalcRecord) -> list[dict]:
    """错题清单。给结果页展示用，也用于「加入错题本」。"""
    questions = rec.questions or []
    answers = rec.answers or []
    out = []
    for idx, q in enumerate(questions):
        given = answers[idx] if idx < len(answers) else None
        if _is_right(given, str(q.get("answer", ""))):
            continue
        out.append({
            "index": idx,
            "type": q.get("type"),
            "stem": q.get("stem"),
            "your_answer": given,
            "right_answer": str(q.get("answer", "")),
        })
    return out


# ---------------------------------------------------------------- 加入错题本

def to_mistakes(db: Session, rec: CalcRecord, indexes: list[int] | None = None) -> list[Mistake]:
    """把本轮错题加进错题本。indexes 为空表示「全部错题」。

    默认不自动入库（M3 定稿）：一轮错 8 道就是 8 条新错题，
    错题本会迅速膨胀到没人看。由孩子在结果页手动挑，家长也可以在家长端补。
    """
    questions = rec.questions or []
    targets = wrong_items(rec)
    if indexes is not None:
        wanted = set(indexes)
        targets = [w for w in targets if w["index"] in wanted]
    if not targets:
        return []

    created: list[Mistake] = []
    for item in targets:
        q = questions[item["index"]]
        m = Mistake(
            child_id=rec.child_id,
            subject="数学",
            point="口算",
            stem=item["stem"],
            answer_own=item["your_answer"],
            answer_right=item["right_answer"],
            cause="计算错",
            source="calc",
            stage=0,
            # 与 mistake_service 的节奏保持一致：录入当天不计次，明天第一次复习
            due_date=_tomorrow(),
            mastered=False,
        )
        db.add(m)
        created.append(m)

    db.flush()
    from app.models.entities import MistakeLog

    for m in created:
        db.add(MistakeLog(mistake_id=m.id, action="add", answer=m.answer_own))
    db.commit()
    for m in created:
        db.refresh(m)
    return created


def _tomorrow():
    from datetime import date, timedelta

    from app.core.clock import local_today

    return local_today() + timedelta(days=1)


# ---------------------------------------------------------------- 查询

def list_rounds(db: Session, child_id: int, *, limit: int = 20, done_only: bool = True) -> list[CalcRecord]:
    stmt = select(CalcRecord).where(CalcRecord.child_id == child_id)
    if done_only:
        stmt = stmt.where(CalcRecord.status == "done")
    return list(db.scalars(stmt.order_by(CalcRecord.id.desc()).limit(limit)))


def rounds_created_between(db: Session, child_id: int, start: datetime) -> int:
    """今天已出过几轮。用来判断「每天第一次口算才发星」将来要不要做。"""
    rows = db.scalars(
        select(CalcRecord.id).where(
            CalcRecord.child_id == child_id, CalcRecord.created_at >= start
        )
    )
    return len(list(rows))
