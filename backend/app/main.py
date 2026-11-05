"""应用入口。

启动顺序：建数据目录 → 起调度器 → 挂路由。
uvicorn 只跑单进程（--workers 1），这是 APScheduler 方案成立的前提，
见 app/tasks/scheduler.py 顶部说明。
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.tasks.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    logging.getLogger(__name__).info("数据目录：%s", settings.DATA_ROOT)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    description="小学学习工作台 · M0 骨架",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # 只放行本地开发端口；上云后改成同源反代，这里可以整段删掉
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,   # Cookie 鉴权需要，见 v1.1 缺口 1 的 img 401 问题
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root():
    return {"ok": True, "app": settings.APP_NAME, "docs": "/docs", "health": "/api/v1/health"}


# 直接运行本文件即可起服务：IDE 里点绿三角，或命令行 python -m app.main
# 注意：必须传 import 字符串 "app.main:app" 而不是 app 对象，否则 reload 不生效；
# reload_dirs 限定为 app，避免监视 .venv（pip 装包会触发无意义的重启）
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=["app"],
    )
