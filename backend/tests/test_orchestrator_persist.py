import inspect
from app.pipeline import orchestrator


def test_orchestrator_no_longer_deletes_all_news_for_day():
    src = inspect.getsource(orchestrator._run_daily_async)
    assert "upsert_rss_items" in src
    # ensure bulk day delete is gone (normalize spaces)
    compact = src.replace(" ", "").replace("\n", "")
    assert "NewsItem.date==target_date).delete()" not in compact
