"""测试共用夹具。

两条取舍：

1. **不建独立的测试库**。study 账号只有 study_table 的权限，建不了新库；
   而自用项目的数据量下，用唯一用户名隔离 + 用例结束删账号（级联删孩子）
   已经足够干净，比为此去要 root 权限划算。
2. **不用 with TestClient(app)**。那会触发 lifespan，每次起停 APScheduler，
   用例一多就变慢且偶发报错。测试只关心接口行为，不关心定时任务。
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.core.security import hash_secret
from app.main import app
from app.models import Account, Child

PASSWORD = "pytest-pass-2026"


@pytest.fixture
def account_factory():
    """按需创建账号（可带孩子），用例结束统一清理。"""
    created: list[int] = []

    def make(with_child: bool = True, child_name: str = "测试娃") -> dict:
        username = f"pytest_{uuid.uuid4().hex[:8]}"
        with SessionLocal() as db:
            acc = Account(
                username=username,
                password_hash=hash_secret(PASSWORD),
                nickname="测试家长",
            )
            db.add(acc)
            db.commit()
            db.refresh(acc)
            child_id = None
            if with_child:
                child = Child(
                    account_id=acc.id, name=child_name, grade=3, edition="人教版"
                )
                db.add(child)
                db.commit()
                db.refresh(child)
                child_id = child.id
            created.append(acc.id)
            return {"username": username, "account_id": acc.id, "child_id": child_id}

    yield make

    with SessionLocal() as db:
        for account_id in created:
            acc = db.get(Account, account_id)
            if acc is not None:
                db.delete(acc)   # child 由外键 ON DELETE CASCADE 一起清掉
        db.commit()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_client(account_factory):
    """已登录的客户端 + 它对应的账号信息。TestClient 会自动保存 Cookie。"""
    info = account_factory()
    c = TestClient(app)
    r = c.post(
        "/api/v1/auth/login",
        json={"username": info["username"], "password": PASSWORD},
    )
    assert r.status_code == 200, r.text
    return c, info
