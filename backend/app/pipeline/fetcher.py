import asyncio
import feedparser
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Optional

from ..utils.http import make_async_client
from ..utils.logger import get_logger

logger = get_logger(__name__)

_SEMAPHORE_LIMIT = 10
_DEDUP_LOOKBACK_DAYS = 14
_DEDUP_CHUNK = 500


@dataclass
class FeedEntry:
    guid: str
    title: str
    link: str
    published_at: Optional[datetime]
    raw_summary: Optional[str]


def _parse_feed_content(content: bytes, url: str) -> list[FeedEntry]:
    feed = feedparser.parse(content)
    entries = []
    for entry in feed.entries:
        guid = entry.get("id") or entry.get("link", "")
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue

        published_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        raw_summary = entry.get("summary", "") or ""
        raw_summary = re.sub(r"<[^>]+>", "", raw_summary).strip()[:500]

        entries.append(FeedEntry(
            guid=guid,
            title=title,
            link=link,
            published_at=published_at,
            raw_summary=raw_summary or None,
        ))
    return entries


async def fetch_source_async(url: str, use_proxy: bool, semaphore: asyncio.Semaphore) -> tuple[str, list[FeedEntry] | None]:
    """异步拉取单个 RSS 源，返回 (url, entries)，失败返回 (url, None)。"""
    async with semaphore:
        try:
            async with make_async_client(use_proxy=use_proxy, timeout=15.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content = resp.content
            entries = _parse_feed_content(content, url)
            logger.info(f"拉取完成 {url}：{len(entries)} 条")
            return url, entries
        except Exception as e:
            logger.warning(f"拉取失败 {url}: {e}")
            return url, None


async def fetch_all_sources_async(sources: list) -> dict[int, list[FeedEntry]]:
    """并发拉取所有启用的源，返回 {source_id: [entries]}。失败源记录 status=failed。"""
    semaphore = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    tasks = [
        fetch_source_async(src.url, src.use_proxy, semaphore)
        for src in sources
    ]
    results = await asyncio.gather(*tasks)

    url_to_source = {src.url: src for src in sources}
    source_entries: dict[int, list[FeedEntry]] = {}

    for url, entries in results:
        src = url_to_source.get(url)
        if src is None:
            continue
        src.last_fetched_at = datetime.now(timezone.utc)
        if entries is None:
            src.last_status = "failed"
        else:
            src.last_status = "ok"
            source_entries[src.id] = entries

    return source_entries


def fetch_and_save(db, source) -> int:
    """同步拉取单个源并写入 raw_articles，兼容 Phase 1 调用。"""
    from ..models import RawArticle

    loop = asyncio.new_event_loop()
    sem = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    try:
        url, entries = loop.run_until_complete(fetch_source_async(source.url, source.use_proxy, sem))
    finally:
        loop.close()

    source.last_fetched_at = datetime.utcnow()
    if entries is None:
        source.last_status = "failed"
        db.commit()
        return 0

    source.last_status = "ok"
    new_count = 0
    for e in entries:
        if db.query(RawArticle).filter_by(link=e.link).first():
            continue
        if db.query(RawArticle).filter_by(source_id=source.id, guid=e.guid).first():
            continue
        db.add(RawArticle(
            source_id=source.id,
            guid=e.guid,
            title=e.title,
            link=e.link,
            published_at=e.published_at,
            raw_summary=e.raw_summary,
        ))
        new_count += 1

    db.commit()
    logger.info(f"写入 raw_articles：{new_count} 条新增（源：{source.name}）")
    return new_count


async def fetch_and_save_all_async(db, sources: list) -> dict[str, int]:
    """并发拉取所有源并批量写入 raw_articles，返回 {source_key: new_count}。"""
    from ..models import RawArticle

    enabled_sources = [s for s in sources if s.enabled]
    source_entries = await fetch_all_sources_async(enabled_sources)

    # 去重集合只查最近 14 天（fetched_at 非空、存 UTC 墙钟），避免随全表增长线性变慢
    dedup_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=_DEDUP_LOOKBACK_DAYS)
    existing_links = {
        row[0]
        for row in db.query(RawArticle.link).filter(RawArticle.fetched_at >= dedup_cutoff).all()
    }
    existing_guids = {
        (row[0], row[1])
        for row in db.query(RawArticle.source_id, RawArticle.guid)
        .filter(RawArticle.fetched_at >= dedup_cutoff)
        .all()
    }

    result = {}
    pending: list[tuple] = []
    for src in enabled_sources:
        entries = source_entries.get(src.id)
        if entries is None:
            result[src.key] = 0
            continue
        result[src.key] = 0
        seen_guids = set()
        for e in entries:
            if e.link in existing_links:
                continue
            guid_key = (src.id, e.guid)
            if guid_key in seen_guids or guid_key in existing_guids:
                continue
            seen_guids.add(guid_key)
            existing_links.add(e.link)
            pending.append((src, e))

    # 慢更新源的旧条目可能超出 14 天窗口仍留在 feed 里，窗口漏判会撞 UNIQUE 约束
    # 使整批提交失败，因此对通过初筛的候选按 link/guid 再精确回查一次（代价与候选数成正比）
    stale_links: set[str] = set()
    stale_guids: set[tuple[int, str]] = set()
    if pending:
        links = [e.link for _, e in pending]
        for i in range(0, len(links), _DEDUP_CHUNK):
            chunk = links[i:i + _DEDUP_CHUNK]
            stale_links.update(
                row[0] for row in db.query(RawArticle.link).filter(RawArticle.link.in_(chunk)).all()
            )
        guids = list({e.guid for _, e in pending})
        for i in range(0, len(guids), _DEDUP_CHUNK):
            chunk = guids[i:i + _DEDUP_CHUNK]
            stale_guids.update(
                (row[0], row[1])
                for row in db.query(RawArticle.source_id, RawArticle.guid)
                .filter(RawArticle.guid.in_(chunk))
                .all()
            )

    for src, e in pending:
        if e.link in stale_links or (src.id, e.guid) in stale_guids:
            continue
        db.add(RawArticle(
            source_id=src.id,
            guid=e.guid,
            title=e.title,
            link=e.link,
            published_at=e.published_at,
            raw_summary=e.raw_summary,
        ))
        result[src.key] += 1

    db.commit()
    logger.info(f"全部源拉取完成，各源新增：{result}")
    return result
