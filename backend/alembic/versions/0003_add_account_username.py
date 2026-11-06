"""add account.username

M1 引入了登录，需要一个人人都有的登录标识。
原表只有 phone，且注释写明「本机自用可先不填」，不能拿来当登录键。

account 表在加这列时是空的，所以可以直接 NOT NULL，不需要分三步
（先加可空列 → 回填 → 再改非空）。

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-06 09:30:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "account",
        sa.Column(
            "username", sa.String(length=32), nullable=False,
            comment="登录名，唯一；自用场景就是一个固定字符串",
        ),
    )
    # 不显式命名，交给 MySQL 按列名生成 account_username_uq 之外的默认名
    op.create_unique_constraint(None, "account", ["username"])


def downgrade() -> None:
    op.drop_constraint("username", "account", type_="unique")
    op.drop_column("account", "username")
