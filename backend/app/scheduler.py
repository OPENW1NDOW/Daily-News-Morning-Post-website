"""
APScheduler 定时任务：每天 8:00 自动触发流水线。
流水线整体在线程池中执行（asyncio.to_thread），调度期间事件循环保持空闲。
"""
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from .utils.logger import get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")


def _run_pipeline_sync():
    """与 admin._run_pipeline_sync 同构的同步执行体，整体跑在线程池里。"""
    from .db import SessionLocal
    from .pipeline.orchestrator import run_daily, release_pipeline_lock
    from . import rsshub
    rsshub.start()
    db = SessionLocal()
    try:
        counts = run_daily(db, trigger="scheduler")
        logger.info(f"调度完成：{counts}")
    except Exception as e:
        logger.error(f"调度执行失败: {e}", exc_info=True)
    finally:
        release_pipeline_lock()
        db.close()


async def _run_pipeline_job():
    from .pipeline.orchestrator import acquire_pipeline_lock
    if not acquire_pipeline_lock():
        logger.warning("流水线已在运行，跳过本次调度触发")
        return
    logger.info("调度触发：开始执行每日流水线")
    try:
        await asyncio.to_thread(_run_pipeline_sync)
    except Exception as e:
        # _run_pipeline_sync 自身吞异常，走到这里通常是事件循环关闭等极端情况
        logger.error(f"调度线程执行异常: {e}", exc_info=True)


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
