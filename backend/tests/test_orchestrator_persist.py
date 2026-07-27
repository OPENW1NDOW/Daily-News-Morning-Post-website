"""流水线持久化行为测试：同日重跑走稳定键 upsert，收藏项保留、不整日清空。"""
import asyncio
from datetime import datetime, timedelta, timezone

from app.models import Favorite, NewsItem, PipelineRun, RawArticle, Source, User
from app.pipeline import orchestrator
from app.utils.timeutil import business_date


def _summary_payload():
    return {
        "summary": "新一句话摘要",
        "full_summary": "新详细总结",
        "viewpoints": [{"view": "某方观点", "source": "某机构"}],
        "background": "背景补充",
    }


def test_rerun_upserts_in_place_and_keeps_favorited_item(db, monkeypatch):
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    src = Source(key="s1", name="源1", url="https://example.com/rss", enabled=True)
    db.add(src)
    db.flush()

    art = RawArticle(
        source_id=src.id, guid="g1", title="候选新闻",
        link="https://example.com/a",
        published_at=now_utc - timedelta(hours=2),
        full_text="已有正文，跳过提取",
    )
    db.add(art)
    db.flush()

    target = business_date()
    # 上一轮已写入：同 raw_article_id 的旧版本，重跑应原地更新（id 不变）
    old_item = NewsItem(
        date=target, category="ai", importance=10,
        title="旧标题", raw_article_id=art.id, source_links=[],
    )
    # 上一轮的收藏项：本轮不在新结果集，必须保留而不是被整日清空
    fav_item = NewsItem(
        date=target, category="ai", importance=20,
        title="收藏的旧闻", raw_article_id=99999, source_links=[],
    )
    db.add_all([old_item, fav_item])
    db.flush()
    user = User(username="u1", password_hash="x")
    db.add(user)
    db.flush()
    db.add(Favorite(user_id=user.id, news_item_id=fav_item.id))
    db.commit()
    old_id, fav_id = old_item.id, fav_item.id

    async def fake_fetch(_db, _sources):
        return {}

    def fake_classify(_db, articles):
        for a in articles:
            a.category = "ai"
            a.importance = 90
        _db.commit()
        return len(articles), 0

    async def fake_following(*_a, **_k):
        return {"status": "skipped", "written": 0, "error": None}

    monkeypatch.setattr("app.pipeline.fetcher.fetch_and_save_all_async", fake_fetch)
    monkeypatch.setattr("app.pipeline.classifier.classify_articles", fake_classify)
    monkeypatch.setattr("app.pipeline.summarizer.summarize", lambda title, text: _summary_payload())
    monkeypatch.setattr(orchestrator, "run_following_branch", fake_following)

    result = asyncio.run(orchestrator._run_daily_async(db, trigger="manual"))

    assert result["ai"] == 1
    run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    assert run is not None
    assert run.status == "success"

    db.expire_all()
    updated = db.get(NewsItem, old_id)
    assert updated is not None  # 稳定键 (date, raw_article_id) upsert：id 不变
    assert updated.title == "候选新闻"
    assert updated.summary == "新一句话摘要"
    assert updated.importance == 90

    kept = db.get(NewsItem, fav_id)
    assert kept is not None  # 收藏项即使不在新结果集也保留
    assert kept.title == "收藏的旧闻"
    assert db.query(Favorite).filter_by(news_item_id=fav_id).count() == 1

    # 当日 ai 板块只剩「更新后的候选 + 被收藏保护的旧闻」
    ai_items = db.query(NewsItem).filter_by(date=target, category="ai").all()
    assert {n.id for n in ai_items} == {old_id, fav_id}
