"""M3：口算逐题明细 + 错题来源

口算为什么需要这三列：
原来 calc_record 只存「一轮成绩的汇总」（total / right_count / seconds），
没有逐题明细。要在后端出题、后端判分，就必须把「题目 + 答案」留在库里，
只把题目下发给前端——否则答案跟着响应一起到浏览器，孩子按 F12 就能看到。
answers 是交卷时孩子填的，留着才能在结果页逐题回看、也才能一键加错题本。

mistake.source 用来区分「家长录入」和「口算错题加入」，
家长端做错题来源统计时不必猜。

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-10 10:50:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "calc_record",
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="doing",
            comment="本轮状态：doing 出题未交卷 / done 已交卷并判分",
        ),
    )
    op.add_column(
        "calc_record",
        sa.Column(
            "questions", sa.JSON(), nullable=True,
            comment="题目与答案：[{type, stem, answer}]。答案只留库，出题接口不下发",
        ),
    )
    op.add_column(
        "calc_record",
        sa.Column(
            "answers", sa.JSON(), nullable=True,
            comment="孩子逐题作答，未填的为 null；交卷时写入",
        ),
    )
    op.add_column(
        "mistake",
        sa.Column(
            "source", sa.String(16), nullable=False, server_default="manual",
            comment="来源：manual 家长录入 / calc 口算错题加入",
        ),
    )


def downgrade() -> None:
    op.drop_column("mistake", "source")
    op.drop_column("calc_record", "answers")
    op.drop_column("calc_record", "questions")
    op.drop_column("calc_record", "status")
