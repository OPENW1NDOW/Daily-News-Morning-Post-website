from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .db import init_db, SessionLocal, get_db
from .pipeline.sync_sources import sync_sources
from .scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        sync_sources(db)
    finally:
        db.close()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="AI News Aggregator", lifespan=lifespan)

# 缓存 categories.yaml，避免每次请求都读磁盘
import yaml, pathlib
_CATEGORIES_CFG = yaml.safe_load(
    (pathlib.Path(__file__).parent.parent / "config" / "categories.yaml")
    .read_text(encoding="utf-8")
)["categories"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


from .api.news import router as news_router
from .api.admin import router as admin_router
from .api.favorites import router as favorites_router
app.include_router(news_router)
app.include_router(admin_router)
app.include_router(favorites_router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/categories")
def list_categories(db=Depends(get_db)):
    from datetime import date as date_type
    from .models import NewsItem
    from sqlalchemy import func
    today = date_type.today()
    counts = dict(
        db.query(NewsItem.category, func.count(NewsItem.id))
        .filter(NewsItem.date == today)
        .group_by(NewsItem.category)
        .all()
    )
    return [
        {
            "key": c["key"],
            "name": c["name"],
            "description": c.get("description", ""),
            "count": counts.get(c["key"], 0),
        }
        for c in _CATEGORIES_CFG
    ]
