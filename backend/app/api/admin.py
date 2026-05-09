"""
Admin API：手动触发流水线 + 状态查询。
"""
import asyncio
from datetime import date
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import NewsItem, Source
from ..utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

# 全局运行状态，防止重复触发
_pipeline_running = False
_last_run_result: dict | None = None


def _run_pipeline_sync(db_factory):
    global _pipeline_running, _last_run_result
    from ..pipeline.orchestrator import run_daily
    db = db_factory()
    try:
        counts = run_daily(db)
        _last_run_result = {"status": "done", "counts": counts}
        logger.info(f"手动触发流水线完成：{counts}")
    except Exception as e:
        _last_run_result = {"status": "error", "error": str(e)}
        logger.error(f"手动触发流水线失败: {e}", exc_info=True)
    finally:
        _pipeline_running = False
        db.close()


@router.post("/api/admin/refresh")
def refresh(background_tasks: BackgroundTasks):
    global _pipeline_running
    if _pipeline_running:
        return {"status": "already_running", "message": "流水线正在运行中，请勿重复触发"}
    _pipeline_running = True
    from ..db import SessionLocal
    background_tasks.add_task(_run_pipeline_sync, SessionLocal)
    return {"status": "started", "message": "流水线已在后台启动"}


@router.get("/api/admin/status")
def status(db: Session = Depends(get_db)):
    today = date.today()
    today_count = db.query(NewsItem).filter(NewsItem.date == today).count()

    sources = db.query(Source).all()
    source_list = [
        {
            "key": s.key,
            "name": s.name,
            "enabled": s.enabled,
            "last_status": s.last_status,
            "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
        }
        for s in sources
    ]

    from ..pipeline.orchestrator import get_pipeline_progress
    progress = get_pipeline_progress()

    return {
        "today_count": today_count,
        "pipeline_running": _pipeline_running,
        "last_run": _last_run_result,
        "sources": source_list,
        "progress": progress if _pipeline_running else None,
    }
