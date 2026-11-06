"""演示数据：一个家长账号 + 一个孩子。

用法（在 backend 目录下）：
    .venv/bin/python -m scripts.seed
    .venv/bin/python -m scripts.seed --reset     # 先删掉同名账号再重建

幂等：账号已存在就不重建，只补齐缺失的孩子，避免把改过的密码覆盖掉。
登录名与口令可用环境变量覆盖：SEED_USER / SEED_PASS。
"""
import argparse
import os
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_secret
from app.models import Account, Child

USERNAME = os.getenv("SEED_USER", "parent")
PASSWORD = os.getenv("SEED_PASS", "study123")
CHILD_NAME = os.getenv("SEED_CHILD", "小明")


def main() -> int:
    parser = argparse.ArgumentParser(description="写入演示账号与孩子档案")
    parser.add_argument("--reset", action="store_true", help="先删除同名账号（级联删孩子）")
    args = parser.parse_args()

    with SessionLocal() as db:
        account = db.scalar(select(Account).where(Account.username == USERNAME))

        if account and args.reset:
            print(f"删除已有账号 {USERNAME} …")
            db.delete(account)
            db.commit()
            account = None

        if account is None:
            account = Account(
                username=USERNAME,
                password_hash=hash_secret(PASSWORD),
                nickname="妈妈",
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            print(f"已创建账号 {USERNAME}（口令 {PASSWORD}）")
        else:
            print(f"账号 {USERNAME} 已存在，保留原口令")
            # 口令忘了可以显式重置：--reset 会重建，或自行改库

        children = db.scalars(
            select(Child).where(Child.account_id == account.id)
        ).all()
        if not children:
            child = Child(
                account_id=account.id, name=CHILD_NAME, grade=3, edition="人教版"
            )
            db.add(child)
            db.commit()
            db.refresh(child)
            print(f"已创建孩子 {child.name}（{child.grade} 年级 · {child.edition}）id={child.id}")
        else:
            for c in children:
                print(f"孩子已存在：{c.name}（{c.grade} 年级 · {c.edition}）id={c.id}")

        print(f"\n登录：用户名 {USERNAME} / 口令 {PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
