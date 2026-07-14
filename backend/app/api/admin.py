"""
Admin API：流水线控制、数据源管理、新闻管理、用户管理、板块管理、系统设置。
旧端点 /api/admin/refresh 和 /api/admin/status 保持无鉴权（兼容首页自动触发）。
"""
import asyncio
import pathlib
import threading
from datetime import date, datetime

import yaml
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db, SessionLocal
from ..models import NewsItem, Source, User, Favorite, PipelineRun, XAccount
from ..schemas import (
    SourceUpdate, NewsUpdate, AdminToggle, CategoryUpdate, SettingsUpdate,
    XAccountEnabledUpdate,
)
from ..utils.logger import get_logger
from ..utils.timeutil import business_date
from .deps import require_admin

router = APIRouter()
logger = get_logger(__name__)

# ── 全局运行状态（兼容旧端点） ──────────────────────────────
_pipeline_running = False
_pipeline_lock = threading.Lock()
_last_run_result: dict | None = None

_CONFIG_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "config"


# ═══════════════════════════════════════════════════════════
#  旧端点（无鉴权，兼容首页自动触发）
# ═══════════════════════════════════════════════════════════

def _run_pipeline_sync(db_factory):
    global _pipeline_running, _last_run_result
    from ..pipeline.orchestrator import run_daily
    from .. import rsshub
    rsshub.start()
    db = db_factory()
    try:
        counts = run_daily(db, trigger="manual")
        _last_run_result = {"status": "done", "counts": counts}
        logger.info(f"手动触发流水线完成：{counts}")
    except Exception as e:
        _last_run_result = {"status": "error", "error": str(e)}
        logger.error(f"手动触发流水线失败: {e}", exc_info=True)
    finally:
        with _pipeline_lock:
            _pipeline_running = False
        db.close()


@router.post("/api/admin/refresh")
def refresh(background_tasks: BackgroundTasks):
    global _pipeline_running
    with _pipeline_lock:
        if _pipeline_running:
            return {"status": "already_running", "message": "流水线正在运行中，请勿重复触发"}
        _pipeline_running = True
    background_tasks.add_task(_run_pipeline_sync, SessionLocal)
    return {"status": "started", "message": "流水线已在后台启动"}


@router.get("/api/admin/status")
def status(db: Session = Depends(get_db)):
    today = business_date()
    today_count = db.query(NewsItem).filter(NewsItem.date == today).count()
    sources = db.query(Source).all()
    source_list = [
        {
            "key": s.key, "name": s.name, "enabled": s.enabled,
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


# ═══════════════════════════════════════════════════════════
#  仪表盘
# ═══════════════════════════════════════════════════════════

@router.get("/api/admin/dashboard")
def dashboard(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    today = business_date()
    today_count = db.query(NewsItem).filter(NewsItem.date == today).count()
    user_count = db.query(User).count()
    total_news = db.query(NewsItem).count()

    # 源健康统计
    sources_ok = db.query(Source).filter(Source.last_status == "ok").count()
    sources_failed = db.query(Source).filter(Source.last_status == "error").count()
    sources_total = db.query(Source).count()

    # 今日分类分布
    cat_counts = (
        db.query(NewsItem.category, func.count(NewsItem.id))
        .filter(NewsItem.date == today)
        .group_by(NewsItem.category)
        .all()
    )
    # 加载分类名称
    categories_cfg = yaml.safe_load((_CONFIG_DIR / "categories.yaml").read_text(encoding="utf-8"))["categories"]
    cat_name_map = {c["key"]: c["name"] for c in categories_cfg}
    category_distribution = [
        {"key": k, "name": cat_name_map.get(k, k), "count": c}
        for k, c in cat_counts
    ]

    # 最近一次流水线
    latest_run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    latest_pipeline = None
    if latest_run:
        latest_pipeline = {
            "id": latest_run.id,
            "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
            "finished_at": latest_run.finished_at.isoformat() if latest_run.finished_at else None,
            "trigger": latest_run.trigger,
            "status": latest_run.status,
            "result": latest_run.result,
            "error": latest_run.error,
        }

    # 系统信息
    import os
    db_path = settings.database_url.replace("sqlite:///", "")
    db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

    return {
        "today_count": today_count,
        "user_count": user_count,
        "total_news": total_news,
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
        "sources_total": sources_total,
        "category_distribution": category_distribution,
        "latest_pipeline": latest_pipeline,
        "system": {
            "llm_model": settings.llm_model,
            "proxy_url": settings.proxy_url,
            "db_size_mb": round(db_size / 1024 / 1024, 2),
        },
    }


# ═══════════════════════════════════════════════════════════
#  流水线控制（带鉴权）
# ═══════════════════════════════════════════════════════════

@router.post("/api/admin/pipeline/trigger")
def admin_trigger_pipeline(background_tasks: BackgroundTasks, user: User = Depends(require_admin)):
    global _pipeline_running
    with _pipeline_lock:
        if _pipeline_running:
            return {"status": "already_running", "message": "流水线正在运行中"}
        _pipeline_running = True
    background_tasks.add_task(_run_pipeline_sync, SessionLocal)
    return {"status": "started", "message": "流水线已在后台启动"}


@router.get("/api/admin/pipeline/status")
def admin_pipeline_status(user: User = Depends(require_admin)):
    from ..pipeline.orchestrator import get_pipeline_progress
    progress = get_pipeline_progress()
    return {
        "pipeline_running": _pipeline_running,
        "progress": progress if _pipeline_running else None,
        "last_run": _last_run_result,
    }


@router.get("/api/admin/pipeline/history")
def admin_pipeline_history(page: int = 1, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    per_page = 20
    total = db.query(PipelineRun).count()
    pages = max(1, (total + per_page - 1) // per_page)
    items = (
        db.query(PipelineRun)
        .order_by(PipelineRun.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": [
            {
                "id": r.id,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "trigger": r.trigger,
                "status": r.status,
                "result": r.result,
                "error": r.error,
            }
            for r in items
        ],
        "total": total,
        "page": page,
        "pages": pages,
    }


# ═══════════════════════════════════════════════════════════
#  数据源管理
# ═══════════════════════════════════════════════════════════

@router.get("/api/admin/sources")
def list_sources(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    sources = db.query(Source).order_by(Source.id).all()
    return [
        {
            "id": s.id, "key": s.key, "name": s.name, "url": s.url,
            "use_proxy": s.use_proxy, "enabled": s.enabled,
            "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
            "last_status": s.last_status,
        }
        for s in sources
    ]


def _sync_source_to_yaml(source_key: str, updates: dict):
    """将数据源变更同步回 sources.yaml"""
    yaml_path = _CONFIG_DIR / "sources.yaml"
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    for src in cfg["sources"]:
        if src["key"] == source_key:
            for k, v in updates.items():
                src[k] = v
            break
    yaml_path.write_text(
        yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


@router.patch("/api/admin/sources/{source_id}")
def update_source(source_id: int, body: SourceUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "数据源不存在")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(source, k, v)
    db.commit()
    db.refresh(source)
    # 同步到 YAML
    yaml_updates = {}
    if "name" in updates: yaml_updates["name"] = updates["name"]
    if "url" in updates: yaml_updates["url"] = updates["url"]
    if "enabled" in updates: yaml_updates["enabled"] = updates["enabled"]
    if "use_proxy" in updates: yaml_updates["use_proxy"] = updates["use_proxy"]
    if yaml_updates:
        _sync_source_to_yaml(source.key, yaml_updates)
    return {
        "id": source.id, "key": source.key, "name": source.name, "url": source.url,
        "use_proxy": source.use_proxy, "enabled": source.enabled,
        "last_fetched_at": source.last_fetched_at.isoformat() if source.last_fetched_at else None,
        "last_status": source.last_status,
    }


@router.post("/api/admin/sources/{source_id}/test")
async def test_source(source_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "数据源不存在")
    from ..utils.http import make_async_client
    url = source.url.replace("${RSSHUB_BASE_URL}", settings.rsshub_base_url)
    try:
        async with make_async_client(use_proxy=source.use_proxy, timeout=12.0) as client:
            resp = await client.get(url)
            ok = resp.status_code < 400
            return {"ok": ok, "status": resp.status_code, "error": None}
    except Exception as e:
        return {"ok": False, "status": None, "error": str(e)[:80]}


# ═══════════════════════════════════════════════════════════
#  新闻管理
# ═══════════════════════════════════════════════════════════

@router.get("/api/admin/news")
def list_news_admin(
    date_str: str | None = None,
    category: str | None = None,
    page: int = 1,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    per_page = 20
    q = db.query(NewsItem)
    if date_str:
        try:
            target = date.fromisoformat(date_str)
            q = q.filter(NewsItem.date == target)
        except ValueError:
            pass
    if category:
        q = q.filter(NewsItem.category == category)
    total = q.count()
    pages = max(1, (total + per_page - 1) // per_page)
    items = q.order_by(NewsItem.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [
            {
                "id": n.id, "date": n.date.isoformat(), "category": n.category,
                "importance": n.importance, "title": n.title, "summary": n.summary,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in items
        ],
        "total": total,
        "page": page,
        "pages": pages,
    }


@router.get("/api/admin/news/{news_id}")
def get_news_admin(news_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.get(NewsItem, news_id)
    if not item:
        raise HTTPException(404, "新闻不存在")
    return {
        "id": item.id, "date": item.date.isoformat(), "category": item.category,
        "importance": item.importance, "title": item.title,
        "summary": item.summary, "full_summary": item.full_summary,
        "viewpoints": item.viewpoints, "background": item.background,
        "source_links": item.source_links,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.patch("/api/admin/news/{news_id}")
def update_news(news_id: int, body: NewsUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.get(NewsItem, news_id)
    if not item:
        raise HTTPException(404, "新闻不存在")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id, "date": item.date.isoformat(), "category": item.category,
        "importance": item.importance, "title": item.title, "summary": item.summary,
    }


@router.delete("/api/admin/news/{news_id}")
def delete_news(news_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    item = db.get(NewsItem, news_id)
    if not item:
        raise HTTPException(404, "新闻不存在")
    # 先删除关联的收藏
    db.query(Favorite).filter(Favorite.news_item_id == news_id).delete()
    db.delete(item)
    db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
#  用户管理
# ═══════════════════════════════════════════════════════════

@router.get("/api/admin/users")
def list_users(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.id).all()
    return [
        {
            "id": u.id, "username": u.username, "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "favorite_count": len(u.favorites),
        }
        for u in users
    ]


@router.patch("/api/admin/users/{target_user_id}/admin")
def toggle_admin(target_user_id: int, body: AdminToggle, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if user.id == target_user_id and not body.is_admin:
        raise HTTPException(400, "不能取消自己的管理员权限")
    target = db.get(User, target_user_id)
    if not target:
        raise HTTPException(404, "用户不存在")
    target.is_admin = body.is_admin
    db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
#  板块管理
# ═══════════════════════════════════════════════════════════

@router.get("/api/admin/categories")
def list_categories_admin(user: User = Depends(require_admin)):
    cfg = yaml.safe_load((_CONFIG_DIR / "categories.yaml").read_text(encoding="utf-8"))
    return cfg["categories"]


@router.patch("/api/admin/categories/{key}")
def update_category(key: str, body: CategoryUpdate, user: User = Depends(require_admin)):
    yaml_path = _CONFIG_DIR / "categories.yaml"
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    found = False
    for cat in cfg["categories"]:
        if cat["key"] == key:
            updates = body.model_dump(exclude_unset=True)
            for k, v in updates.items():
                cat[k] = v
            found = True
            break
    if not found:
        raise HTTPException(404, "板块不存在")
    yaml_path.write_text(
        yaml.dump(cfg, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    # 更新内存缓存
    from ..main import _CATEGORIES_CFG
    for cached in _CATEGORIES_CFG:
        if cached["key"] == key:
            for k, v in updates.items():
                cached[k] = v
            return cached
    return {"key": key}


# ═══════════════════════════════════════════════════════════
#  系统设置
# ═══════════════════════════════════════════════════════════

@router.get("/api/admin/settings")
def get_settings(user: User = Depends(require_admin)):
    masked_key = "****" + settings.llm_api_key[-4:] if len(settings.llm_api_key) > 4 else "****"
    return {
        "llm_api_key_masked": masked_key,
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "proxy_url": settings.proxy_url,
    }


@router.patch("/api/admin/settings")
def update_settings(body: SettingsUpdate, user: User = Depends(require_admin)):
    env_path = pathlib.Path(__file__).resolve().parent.parent.parent / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updates = body.model_dump(exclude_unset=True)
    env_keys = {"llm_api_key": "LLM_API_KEY", "llm_base_url": "LLM_BASE_URL", "llm_model": "LLM_MODEL", "proxy_url": "PROXY_URL"}
    changed_keys = set()
    for field, value in updates.items():
        env_key = env_keys.get(field)
        if not env_key:
            continue
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{env_key}="):
                lines[i] = f"{env_key}={value}"
                found = True
                break
        if not found:
            lines.append(f"{env_key}={value}")
        changed_keys.add(env_key)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"message": f"已更新 {', '.join(changed_keys)}。部分设置需要重启服务才能生效。"}


# ═══════════════════════════════════════════════════════════
#  X Following 账号管理
# ═══════════════════════════════════════════════════════════

def _x_account_dict(a: XAccount) -> dict:
    return {
        "id": a.id,
        "x_user_id": a.x_user_id,
        "handle": a.handle,
        "display_name": a.display_name,
        "avatar_url": a.avatar_url,
        "enabled": a.enabled,
        "is_following": a.is_following,
        "first_seen_at": a.first_seen_at.isoformat() if a.first_seen_at else None,
        "last_synced_at": a.last_synced_at.isoformat() if a.last_synced_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


@router.get("/api/admin/x-following/accounts")
def list_x_following_accounts(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    accounts = db.query(XAccount).order_by(XAccount.id).all()
    return [_x_account_dict(a) for a in accounts]


@router.patch("/api/admin/x-following/accounts/{account_id}")
def update_x_following_account(
    account_id: int,
    body: XAccountEnabledUpdate,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = db.get(XAccount, account_id)
    if not account:
        raise HTTPException(404, "账号不存在")
    account.enabled = body.enabled
    db.commit()
    db.refresh(account)
    return _x_account_dict(account)


@router.post("/api/admin/x-following/sync")
def sync_x_following(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    from ..pipeline.sync_x_following import sync_following_accounts
    try:
        sync_following_accounts(db)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"X Following 同步失败: {e}", exc_info=True)
        raise HTTPException(500, f"同步失败: {e}")
    count = db.query(XAccount).filter(XAccount.is_following.is_(True)).count()
    return {"status": "ok", "count": count}


@router.get("/api/admin/x-following/status")
def x_following_status(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    cookie_configured = bool(settings.x_auth_token and settings.x_ct0)
    max_synced = db.query(func.max(XAccount.last_synced_at)).scalar()
    latest_run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    following = None
    if latest_run and isinstance(latest_run.result, dict):
        following = latest_run.result.get("following")
    return {
        "cookie_configured": cookie_configured,
        "last_synced_at": max_synced.isoformat() if max_synced else None,
        "following": following,
    }
