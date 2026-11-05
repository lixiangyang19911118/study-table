"""健康检查：一行命令就能确认「服务活着、库连得上、目录可写」。"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.integrations.storage import get_storage

router = APIRouter(tags=["系统"])


@router.get("/health", summary="服务与依赖状态")
def health(db: Session = Depends(get_db)):
    db_ok, db_err = True, None
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001 —— 健康检查要吞异常并如实报告
        db_ok, db_err = False, type(e).__name__

    storage = get_storage()
    writable = True
    try:
        probe = settings.DATA_ROOT / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        writable = False

    return {
        "app": settings.APP_NAME,
        "env": settings.ENV,
        "db": {"ok": db_ok, "error": db_err},
        "storage": {
            "root": str(settings.DATA_ROOT),
            "writable": writable,
            **storage.stats(),
        },
        "scheduler": settings.SCHEDULER_ENABLED,
    }


@router.get("/meta", summary="前端启动时拉取的运行时元信息")
def meta():
    return {
        "app": settings.APP_NAME,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "timezone": settings.TIMEZONE,
        "data_root": str(settings.DATA_ROOT),
    }
