"""时区窗口回归：published_at 存 UTC 墙钟，CST 窗口边界必须先转 UTC 再比较。
修复前 CST 墙钟直接与 UTC 墙钟比较，窗口整体错位 8 小时，
20 小时前发布的文章会被漏出 24 小时窗口。"""
import asyncio
from datetime import datetime, timedelta, timezone

from app.models import RawArticle, Source
from app.pipeline import orchestrator
from app.utils.timeutil import CST, business_date


def test_20h_old_utc_article_falls_in_24h_window(db, monkeypatch):
    src = Source(key="s1", name="源1", url="https://example.com/rss", enabled=True)
    db.add(src)
    db.flush()

    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    in_window = RawArticle(
        source_id=src.id, guid="g-20h", title="二十小时前",
        link="https://example.com/a",
        published_at=now_utc - timedelta(hours=20),
    )
    out_window = RawArticle(
        source_id=src.id, guid="g-30h", title="三十小时前",
        link="https://example.com/b",
        published_at=now_utc - timedelta(hours=30),
    )
    db.add_all([in_window, out_window])
    db.commit()

    seen: dict = {}

    async def fake_fetch(_db, _sources):
        return {}

    def fake_classify(_db, articles):
        seen["titles"] = {a.title for a in articles}
        return 0, 0  # 不设置 category，后续步骤空跑

    monkeypatch.setattr("app.pipeline.fetcher.fetch_and_save_all_async", fake_fetch)
    monkeypatch.setattr("app.pipeline.classifier.classify_articles", fake_classify)

    now_cst = datetime.now(CST)
    day_start = now_cst - timedelta(hours=orchestrator.LOOKBACK_HOURS)
    counts, failed_batches = asyncio.run(
        orchestrator._run_rss_pipeline(db, business_date(now_cst), day_start, now_cst)
    )

    assert "二十小时前" in seen["titles"]  # 修复前会被 8 小时错位漏掉
    assert "三十小时前" not in seen["titles"]
    assert failed_batches == 0
