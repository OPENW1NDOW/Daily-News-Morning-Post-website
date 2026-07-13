"""Following 旁路 + orchestrator 接线测试。"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.models import PipelineRun
from app.pipeline import following_branch, orchestrator
from app.pipeline.bird_client import BirdAuthError


def test_cookie_empty_skips(db, monkeypatch):
    monkeypatch.setattr("app.pipeline.following_branch.settings.x_auth_token", "")
    monkeypatch.setattr("app.pipeline.following_branch.settings.x_ct0", "")
    now = datetime.now(timezone.utc)
    result = asyncio.run(
        following_branch.run_following_branch(db, now.date(), now - timedelta(hours=24), now)
    )
    assert result == {"status": "skipped", "written": 0, "error": None}


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
