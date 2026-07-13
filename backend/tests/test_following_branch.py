"""Following 旁路 + orchestrator 接线测试。"""
import asyncio
from datetime import datetime, timedelta, timezone

from app.models import NewsItem, PipelineRun, XAccount
from app.pipeline import following_branch, orchestrator
from app.pipeline.bird_client import BirdAuthError
from app.pipeline.persist import FOLLOWING_CATEGORY


def test_cookie_empty_skips(db, monkeypatch):
    monkeypatch.setattr("app.pipeline.following_branch.settings.x_auth_token", "")
    monkeypatch.setattr("app.pipeline.following_branch.settings.x_ct0", "")
    now = datetime.now(timezone.utc)
    result = asyncio.run(
        following_branch.run_following_branch(db, now.date(), now - timedelta(hours=24), now)
    )
    assert result == {"status": "skipped", "written": 0, "error": None}


def test_disabled_accounts_skip_without_sync(db, monkeypatch):
    monkeypatch.setattr("app.pipeline.following_branch.settings.x_auth_token", "tok")
    monkeypatch.setattr("app.pipeline.following_branch.settings.x_ct0", "ct0")
    db.add(
        XAccount(
            x_user_id="1",
            handle="someone",
            display_name="Someone",
            enabled=False,
            is_following=True,
        )
    )
    db.commit()

    sync_called = {"n": 0}

    def fake_sync(_db):
        sync_called["n"] += 1

    monkeypatch.setattr(following_branch, "sync_following_accounts", fake_sync)

    now = datetime.now(timezone.utc)
    result = asyncio.run(
        following_branch.run_following_branch(db, now.date(), now - timedelta(hours=24), now)
    )
    assert result == {"status": "skipped", "written": 0, "error": None}
    assert sync_called["n"] == 0


def test_following_runs_even_if_mainline_fails(db, monkeypatch):
    async def boom(*_a, **_k):
        raise RuntimeError("rss exploded")

    async def following_ok(*_a, **_k):
        return {"status": "ok", "written": 2, "error": None}

    monkeypatch.setattr(orchestrator, "_run_rss_pipeline", boom)
    monkeypatch.setattr(orchestrator, "run_following_branch", following_ok)

    result = asyncio.run(orchestrator._run_daily_async(db))

    assert result["following"] == {"status": "ok", "written": 2, "error": None}
    run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    assert run is not None
    assert run.status == "error"
    assert "rss exploded" in (run.error or "")
    assert run.result["following"]["status"] == "ok"


def test_rss_dirty_session_still_allows_following_upsert(db, monkeypatch):
    """RSS 脏 session 后 raise → rollback → Following 仍可写入，PipelineRun 可提交。"""

    async def dirty_then_raise(db_sess, *_a, **_k):
        db_sess.add(
            NewsItem(
                date=datetime.now(timezone.utc).date(),
                category="ai",
                importance=1,
                title="orphan-dirty",
            )
        )
        raise RuntimeError("rss dirty fail")

    async def following_writes(db_sess, target_date, *_a, **_k):
        from app.pipeline.persist import upsert_following_items

        written = upsert_following_items(
            db_sess,
            target_date=target_date,
            rows=[{
                "external_id": "tw1",
                "importance": 80,
                "title": "following ok",
                "summary": "sum",
                "full_summary": "sum",
                "viewpoints": None,
                "background": None,
                "handle": "alice",
                "url": "https://x.com/i/status/tw1",
            }],
        )
        db_sess.commit()
        return {"status": "ok", "written": written, "error": None}

    monkeypatch.setattr(orchestrator, "_run_rss_pipeline", dirty_then_raise)
    monkeypatch.setattr(orchestrator, "run_following_branch", following_writes)

    result = asyncio.run(orchestrator._run_daily_async(db))

    assert result["following"]["status"] == "ok"
    assert result["following"]["written"] == 1
    run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    assert run is not None
    assert run.status == "error"
    assert "rss dirty fail" in (run.error or "")
    assert run.result["following"]["status"] == "ok"
    # dirty RSS NewsItem 被 rollback，不应落库；following 应落库
    assert db.query(NewsItem).filter_by(title="orphan-dirty").count() == 0
    assert (
        db.query(NewsItem)
        .filter_by(category=FOLLOWING_CATEGORY, title="following ok")
        .count()
        == 1
    )


def test_bird_failure_does_not_fail_mainline(db, monkeypatch):
    async def rss_ok(*_a, **_k):
        return {}

    async def following_boom(*_a, **_k):
        raise BirdAuthError("bad cookie")

    monkeypatch.setattr(orchestrator, "_run_rss_pipeline", rss_ok)
    monkeypatch.setattr(orchestrator, "run_following_branch", following_boom)

    result = asyncio.run(orchestrator._run_daily_async(db))

    assert result["following"]["status"] == "error"
    assert "bad cookie" in (result["following"]["error"] or "")
    run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    assert run is not None
    assert run.status == "success"
    assert run.result["following"]["status"] == "error"
