"""同步 Session。刻意不用异步 ORM：单机自用用不上，且 asyncmy 在 Py3.13+arm64 上容易卡编译。"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,      # 长时间空闲后 MySQL 断开连接，取连接前先探活
    pool_recycle=3600,       # 早于 MySQL wait_timeout 回收，避免 "MySQL server has gone away"
    pool_size=5,
    max_overflow=5,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
