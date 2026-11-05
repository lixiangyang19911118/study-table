"""单进程调度器。

用 APScheduler 而不是 Celery：只有一个 uvicorn 进程，没有跨进程分发需求，
省掉 Redis 与一个常驻 worker。三个条件满足任一就该换 Celery：
① 起多 worker；② 单次任务耗时超过一分钟；③ 开始对外提供服务。
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.tasks.jobs import scan_due_mistakes, settle_checkin

log = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.SCHEDULER_ENABLED:
        log.info("SCHEDULER_ENABLED=false，跳过定时任务")
        return None
    if _scheduler is not None:
        return _scheduler

    sched = BackgroundScheduler(timezone=settings.TIMEZONE, daemon=True)
    sched.add_job(
        scan_due_mistakes, CronTrigger(hour=0, minute=10),
        id="scan_due_mistakes", replace_existing=True, max_instances=1,
    )
    sched.add_job(
        settle_checkin, CronTrigger(hour=23, minute=55),
        id="settle_checkin", replace_existing=True, max_instances=1,
    )
    sched.start()
    _scheduler = sched
    log.info("调度器已启动：00:10 错题扫描 / 23:55 打卡结算（%s）", settings.TIMEZONE)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
