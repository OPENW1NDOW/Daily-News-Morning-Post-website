"""按稳定键 upsert news_items，避免同日重跑冲掉 favorites。"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..models import Favorite, NewsItem

EXTERNAL_ID_KEY = "external_id"
FOLLOWING_CATEGORY = "following"


def _favorited_ids(db: Session, news_item_ids: list[int]) -> set[int]:
    if not news_item_ids:
        return set()
    rows = (
        db.query(Favorite.news_item_id)
        .filter(Favorite.news_item_id.in_(news_item_ids))
        .all()
    )
    return {r[0] for r in rows}


def _apply_fields(item: NewsItem, row: dict) -> None:
    item.importance = row["importance"]
    item.title = row["title"]
    item.summary = row.get("summary")
    item.full_summary = row.get("full_summary")
    item.viewpoints = row.get("viewpoints")
    item.background = row.get("background")
    item.source_links = row.get("source_links")


def upsert_rss_items(
    db: Session,
    *,
    target_date: date,
    category: str,
    rows: list[dict],
) -> int:
    """稳定键 (date, raw_article_id)。返回写入/更新条数。"""
    existing = (
        db.query(NewsItem)
        .filter(NewsItem.date == target_date, NewsItem.category == category)
        .all()
    )
    by_raw = {n.raw_article_id: n for n in existing if n.raw_article_id is not None}
    keep_raw_ids: set[int] = set()
    written = 0

    for row in rows:
        rid = row["raw_article_id"]
        keep_raw_ids.add(rid)
        item = by_raw.get(rid)
        if item is None:
            item = NewsItem(
                date=target_date,
                category=category,
                raw_article_id=rid,
                importance=row["importance"],
                title=row["title"],
            )
            db.add(item)
            by_raw[rid] = item
        _apply_fields(item, row)
        written += 1

    fav_ids = _favorited_ids(db, [n.id for n in existing if n.id is not None])
    for n in list(existing):
        if n.raw_article_id in keep_raw_ids:
            continue
        if n.id in fav_ids:
            continue
        db.delete(n)

    db.flush()
    return written


def _external_id_from_item(item: NewsItem) -> str | None:
    links = item.source_links or []
    if not links:
        return None
    ext = links[0].get(EXTERNAL_ID_KEY) if isinstance(links[0], dict) else None
    return str(ext) if ext is not None else None


def upsert_following_items(
    db: Session,
    *,
    target_date: date,
    rows: list[dict],
) -> int:
    """稳定键 (date, category=following, external_id in source_links)。"""
    existing = (
        db.query(NewsItem)
        .filter(NewsItem.date == target_date, NewsItem.category == FOLLOWING_CATEGORY)
        .all()
    )
    by_ext = {}
    for n in existing:
        ext = _external_id_from_item(n)
        if ext:
            by_ext[ext] = n

    keep: set[str] = set()
    written = 0
    for row in rows:
        ext = str(row["external_id"])
        keep.add(ext)
        links = [{
            "name": f"@{row['handle'].lstrip('@')}",
            "url": row["url"],
            EXTERNAL_ID_KEY: ext,
        }]
        payload = {
            "importance": row["importance"],
            "title": row["title"],
            "summary": row.get("summary"),
            "full_summary": row.get("full_summary"),
            "viewpoints": row.get("viewpoints"),
            "background": row.get("background"),
            "source_links": links,
        }
        item = by_ext.get(ext)
        if item is None:
            item = NewsItem(
                date=target_date,
                category=FOLLOWING_CATEGORY,
                raw_article_id=None,
                importance=payload["importance"],
                title=payload["title"],
                source_links=links,
            )
            db.add(item)
            by_ext[ext] = item
        _apply_fields(item, payload)
        written += 1

    fav_ids = _favorited_ids(db, [n.id for n in existing if n.id is not None])
    for n in list(existing):
        ext = _external_id_from_item(n)
        if ext in keep:
            continue
        if n.id in fav_ids:
            continue
        db.delete(n)

    db.flush()
    return written
