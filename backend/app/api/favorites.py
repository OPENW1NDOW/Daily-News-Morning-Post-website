"""收藏 API：添加、删除、列表（按用户隔离）。"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..db import get_db
from ..models import Favorite, NewsItem, User
from ..schemas import NewsItemOut
from .deps import get_current_user, require_user

router = APIRouter()


class FavoriteIn(BaseModel):
    news_item_id: int


def _news_with_favorited(item: NewsItem, fav_ids: set) -> dict:
    d = NewsItemOut.model_validate(item).model_dump()
    d["is_favorited"] = item.id in fav_ids
    return d


@router.post("/api/favorites")
def add_favorite(body: FavoriteIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    if not db.query(NewsItem).filter_by(id=body.news_item_id).first():
        raise HTTPException(status_code=404, detail="新闻不存在")
    existing = db.query(Favorite).filter_by(user_id=user.id, news_item_id=body.news_item_id).first()
    if existing:
        return {"id": existing.id}
    fav = Favorite(user_id=user.id, news_item_id=body.news_item_id, favorited_at=datetime.now())
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return {"id": fav.id}


@router.delete("/api/favorites/{news_item_id}")
def remove_favorite(news_item_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    fav = db.query(Favorite).filter_by(user_id=user.id, news_item_id=news_item_id).first()
    if not fav:
        raise HTTPException(status_code=404, detail="收藏不存在")
    db.delete(fav)
    db.commit()
    return {"ok": True}


@router.get("/api/favorites")
def list_favorites(page: int = 1, user: User = Depends(require_user), db: Session = Depends(get_db)):
    per_page = 20
    query = db.query(Favorite).filter_by(user_id=user.id)
    total = query.count()
    favs = (
        query.order_by(Favorite.favorited_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    fav_ids = {f.news_item_id for f in db.query(Favorite).filter_by(user_id=user.id).all()}
    items = []
    for fav in favs:
        item = db.query(NewsItem).filter_by(id=fav.news_item_id).first()
        if item:
            items.append(_news_with_favorited(item, fav_ids))
    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": (total + per_page - 1) // per_page,
    }
