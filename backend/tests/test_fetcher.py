"""fetcher 去重回归：同 link 跨源、(source_id, guid) 唯一、批内重复、超窗口旧条目回查。"""
import asyncio
from datetime import datetime, timedelta, timezone

from app.models import RawArticle, Source
from app.pipeline import fetcher
from app.pipeline.fetcher import FeedEntry, fetch_and_save_all_async


def _utc_naive(**delta) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(**delta)


def _entry(guid: str, link: str, title: str = "标题") -> FeedEntry:
    return FeedEntry(
        guid=guid,
        title=title,
        link=link,
        published_at=datetime.now(timezone.utc) - timedelta(hours=2),
        raw_summary="摘要",
    )


def _make_sources(db, n: int) -> list[Source]:
    sources = [
        Source(key=f"s{i}", name=f"源{i}", url=f"https://example.com/{i}/rss", enabled=True)
        for i in range(1, n + 1)
    ]
    db.add_all(sources)
    db.commit()
    return sources


def _patch_feed(monkeypatch, mapping: dict):
    async def _fake(_sources):
        return mapping

    monkeypatch.setattr(fetcher, "fetch_all_sources_async", _fake)


def test_same_link_different_sources_written_once(db, monkeypatch):
    s1, s2 = _make_sources(db, 2)
    link = "https://example.com/shared"
    _patch_feed(monkeypatch, {
        s1.id: [_entry("g1", link)],
        s2.id: [_entry("g2", link)],
    })

    result = asyncio.run(fetch_and_save_all_async(db, [s1, s2]))

    assert db.query(RawArticle).filter_by(link=link).count() == 1
    assert result["s1"] + result["s2"] == 1


def test_existing_source_guid_not_rewritten(db, monkeypatch):
    (s1,) = _make_sources(db, 1)
    db.add(RawArticle(
        source_id=s1.id, guid="g1", title="旧文",
        link="https://example.com/old",
        published_at=_utc_naive(hours=5),
        fetched_at=_utc_naive(hours=5),  # 落在 14 天去重窗口内
    ))
    db.commit()

    # 同 (source_id, guid) 但 link 变化（如原文重定向）→ 不应重写
    _patch_feed(monkeypatch, {s1.id: [_entry("g1", "https://example.com/new")]})

    result = asyncio.run(fetch_and_save_all_async(db, [s1]))

    assert result["s1"] == 0
    assert db.query(RawArticle).count() == 1
    assert db.query(RawArticle).one().link == "https://example.com/old"


def test_same_batch_duplicate_guid_written_once(db, monkeypatch):
    (s1,) = _make_sources(db, 1)
    _patch_feed(monkeypatch, {
        s1.id: [
            _entry("g1", "https://example.com/a"),
            _entry("g1", "https://example.com/b"),
        ],
    })

    result = asyncio.run(fetch_and_save_all_async(db, [s1]))

    assert result["s1"] == 1
    assert db.query(RawArticle).filter_by(source_id=s1.id, guid="g1").count() == 1


def test_new_entries_within_window_are_written(db, monkeypatch):
    s1, s2 = _make_sources(db, 2)
    _patch_feed(monkeypatch, {
        s1.id: [_entry("g1", "https://example.com/a"), _entry("g2", "https://example.com/b")],
        s2.id: [_entry("g3", "https://example.com/c")],
    })

    result = asyncio.run(fetch_and_save_all_async(db, [s1, s2]))

    assert result == {"s1": 2, "s2": 1}
    assert db.query(RawArticle).count() == 3


def test_stale_entry_outside_window_still_deduped(db, monkeypatch):
    """慢更新源：旧条目 fetched_at 超出 14 天初筛窗口但仍留在 feed 里，
    精确回查必须拦下它，否则撞 link UNIQUE 约束导致整批提交失败。"""
    (s1,) = _make_sources(db, 1)
    db.add(RawArticle(
        source_id=s1.id, guid="g-old", title="旧文",
        link="https://example.com/stale",
        published_at=_utc_naive(days=30),
        fetched_at=_utc_naive(days=30),
    ))
    db.commit()

    _patch_feed(monkeypatch, {s1.id: [_entry("g-old", "https://example.com/stale")]})

    result = asyncio.run(fetch_and_save_all_async(db, [s1]))

    assert result["s1"] == 0
    assert db.query(RawArticle).count() == 1
