import inspect
from app.pipeline import orchestrator


def test_orchestrator_no_longer_deletes_all_news_for_day():
    src = inspect.getsource(orchestrator._run_rss_pipeline)
    assert "upsert_rss_items" in src
    # ensure bulk day delete is gone (normalize spaces)
    compact = src.replace(" ", "").replace("\n", "")
    assert "NewsItem.date==target_date).delete()" not in compact

    outer = inspect.getsource(orchestrator._run_daily_async)
    compact_outer = outer.replace(" ", "").replace("\n", "")
    assert "NewsItem.date==target_date).delete()" not in compact_outer
    assert "run_following_branch" in outer
