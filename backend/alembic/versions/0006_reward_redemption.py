"""M4：兑换记录表

为什么需要一张新表，而不是直接写 star_ledger：
兑换要「孩子提 → 家长批」，中间有个 pending 状态，流水表表达不了。
pending 期间星星不能真的扣（家长还没答应），但也不能让孩子重复申请
把余额占满——所以「可用余额 = 余额 - 所有 pending 的 cost 之和」。

为什么存 cost / reward_name 快照：
家长事后把「看动画片」从 20 星改成 50 星，历史兑换记录不能跟着变；
删掉奖励项也不该抹掉已发生的账目，reward_id 用 SET NULL 而非 CASCADE。

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-11 09:20:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reward_redemption",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False, comment="主键"),
        sa.Column("child_id", sa.BigInteger(), nullable=False, comment="归属孩子"),
        sa.Column(
            "reward_id", sa.BigInteger(), nullable=True,
            comment="奖励项；奖励被删后置空，历史记录仍保留",
        ),
        sa.Column(
            "reward_name", sa.String(64), nullable=False,
            comment="奖励名称快照，防止改名后历史记录串味",
        ),
        sa.Column(
            "cost", sa.Integer(), nullable=False,
            comment="申请时的星星价快照，防止家长改价影响历史账目",
        ),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="pending",
            comment="状态：pending 待确认 / approved 已批准 / rejected 已拒绝 / cancelled 已撤回",
        ),
        sa.Column("note", sa.String(255), nullable=True, comment="家长留言或拒绝原因"),
        sa.Column("decided_at", sa.DateTime(), nullable=True, comment="家长处理时间；pending 时为空"),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="创建时间（UTC）",
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="最后更新时间（UTC），MySQL 侧带 ON UPDATE",
        ),
        sa.ForeignKeyConstraint(["child_id"], ["child.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reward_id"], ["reward.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        comment="兑换申请：pending 待家长确认，批准时才写负向星星流水",
    )
    op.create_index("ix_redeem_status", "reward_redemption", ["child_id", "status"])
    op.create_index("ix_redeem_time", "reward_redemption", ["child_id", "created_at"])

    # server_default 加的 CURRENT_TIMESTAMP 不带 ON UPDATE，手工补上，
    # 否则 updated_at 永远停在插入那一刻（M3 迁移踩过这个坑）。
    op.execute(
        "ALTER TABLE reward_redemption "
        "MODIFY COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
        "ON UPDATE CURRENT_TIMESTAMP "
        "COMMENT '最后更新时间（UTC），MySQL 侧带 ON UPDATE'"
    )


def downgrade() -> None:
    op.drop_index("ix_redeem_time", table_name="reward_redemption")
    op.drop_index("ix_redeem_status", table_name="reward_redemption")
    op.drop_table("reward_redemption")
