from datetime import date as date_type
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import NewsItem, Favorite
from ..schemas import NewsItemOut

router = APIRouter()


def _with_favorited(items: list[NewsItem], db: Session) -> list[dict]:
    fav_ids = {f.news_item_id for f in db.query(Favorite).all()}
    result = []
    for item in items:
        d = NewsItemOut.model_validate(item).model_dump()
        d["is_favorited"] = item.id in fav_ids
        result.append(d)
    return result


@router.get("/api/news", response_model=list[NewsItemOut])
def list_news(
    date: date_type | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    today = date_type.today()
    q = db.query(NewsItem).filter(NewsItem.date == (date or today))
    if category:
        q = q.filter(NewsItem.category == category)
    items = q.order_by(NewsItem.importance.desc()).limit(6).all()
    return _with_favorited(items, db)


@router.get("/api/news/{item_id}", response_model=NewsItemOut)
def get_news_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(NewsItem).filter(NewsItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    fav = db.query(Favorite).filter_by(news_item_id=item_id).first()
    d = NewsItemOut.model_validate(item).model_dump()
    d["is_favorited"] = fav is not None
    return d
