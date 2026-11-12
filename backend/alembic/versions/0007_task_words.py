"""听写：给 task 加词表字段

为什么不做独立的 word_list 表：
单用户场景下家长一天布置一两个听写，词表用完就过期，建表就要配一整套
增删改查界面；而听写的结果本来就必须挂在任务上（要拍照交、要家长审核、
要发星星）。所以词表直接跟任务走，一次粘贴一份，跑通主链路再谈复用。

为什么用 JSON 而不是逗号分隔的 VARCHAR：
词本身可能带标点、空格（英语短语），分隔符迟早撞车。JSON 数组省掉转义，
也方便前端直接拿数组渲染。

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-12 17:20:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "task",
        sa.Column(
            "words", sa.JSON(), nullable=True,
            comment="听写词表，一行一个词；kind=dictation 时使用，其他类型为空。"
                    "刻意不做独立词表表：单用户一天一两个词表，先挂在任务上跑通",
        ),
    )


def downgrade() -> None:
    op.drop_column("task", "words")
