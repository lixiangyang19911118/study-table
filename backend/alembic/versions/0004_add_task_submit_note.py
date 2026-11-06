"""add task.submit_note

M2 允许「照片或文字二选一」提交，文字需要一个独立的位置。

不复用 task.note：那一列是家长布置任务时的留言，两者会互相覆盖，
而且退回重做时孩子的话要在审核页单独展示。

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-06 11:40:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "task",
        sa.Column(
            "submit_note", sa.Text(), nullable=True,
            comment="孩子提交时写的一句说明；与照片二选一即可满足提交条件，退回时清空",
        ),
    )


def downgrade() -> None:
    op.drop_column("task", "submit_note")
