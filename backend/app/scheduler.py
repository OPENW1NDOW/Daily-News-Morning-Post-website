"""
APScheduler 定时任务：每天 8:00 自动触发流水线。
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .utils.logger import get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


async def _run_pipeline_job():
    from .db import SessionLocal
    from .pipeline.orchestrator import run_daily
    logger.info("调度触发：开始执行每日流水线")
    db = SessionLocal()
    try:
        counts = run_daily(db)
        logger.info(f"调度完成：{counts}")
    except Exception as e:
        logger.error(f"调度执行失败: {e}", exc_info=True)
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        _run_pipeline_job,
        trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Shanghai"),
        id="daily_pipeline",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("调度器已启动，每日 08:00 (Asia/Shanghai) 执行流水线")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("调度器已停止")
