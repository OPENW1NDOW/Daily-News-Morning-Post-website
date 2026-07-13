"""Following 旁路：抓取关注账号推文 → 过滤精选 → upsert news_items。"""
from __future__ import annotations

import asyncio
from datetime import date, datetime

from sqlalchemy.orm import Session

from ..config import settings
from ..models import XAccount
from ..utils.logger import get_logger
from .bird_client import BirdAuthError, fetch_user_tweets
from .following_select import select_tweets
from .persist import upsert_following_items
from .sync_x_following import sync_following_accounts
from .tweet_filter import filter_tweets

logger = get_logger(__name__)

_FETCH_CONCURRENCY = 2
_FINAL_TOP_N = 6


def _enabled_following(db: Session) -> list[XAccount]:
    return (
        db.query(XAccount)
        .filter(XAccount.enabled.is_(True), XAccount.is_following.is_(True))
        .all()
    )


async def run_following_branch(
    db: Session,
    target_date: date,
    day_start: datetime,
    day_end: datetime,
) -> dict:
    """
    Following 旁路入口。
    返回 {status: "ok"|"skipped"|"error", written: int, error: str|None}。
    不写入 raw_articles。
    """
    try:
        if not (settings.x_auth_token or "").strip() or not (settings.x_ct0 or "").strip():
            return {"status": "skipped", "written": 0, "error": None}

        accounts = _enabled_following(db)
        if not accounts:
            try:
                sync_following_accounts(db)
                db.commit()
            except Exception as e:
                logger.exception("Following sync failed")
                return {"status": "error", "written": 0, "error": str(e)[:500]}
            accounts = _enabled_following(db)
            if not accounts:
                return {"status": "skipped", "written": 0, "error": None}

        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)
        since_iso = day_start.isoformat()
        until_iso = day_end.isoformat()

        async def _fetch_one(account: XAccount) -> list[dict]:
            async with sem:
                return await asyncio.to_thread(
                    fetch_user_tweets,
                    account.handle,
                    since_iso,
                    until_iso,
                )

        results = await asyncio.gather(
            *[_fetch_one(a) for a in accounts],
            return_exceptions=True,
        )

        all_tweets: list[dict] = []
        for account, result in zip(accounts, results):
            if isinstance(result, BirdAuthError):
                return {"status": "error", "written": 0, "error": str(result)[:500]}
            if isinstance(result, Exception):
                logger.warning(
                    "fetch tweets failed for @%s: %s",
                    account.handle,
                    result,
                )
                continue
            all_tweets.extend(result)

        filtered = filter_tweets(all_tweets)
        selected = select_tweets(filtered)[:_FINAL_TOP_N]

        rows = []
        for t in selected:
            rows.append({
                "external_id": t["tweet_id"],
                "importance": int(t.get("score") or 50),
                "title": (t.get("summary") or t.get("text") or "")[:120],
                "summary": t.get("summary"),
                "full_summary": t.get("summary"),
                "viewpoints": None,
                "background": None,
                "handle": t["handle"],
                "url": f"https://x.com/i/status/{t['tweet_id']}",
            })

        written = upsert_following_items(db, target_date=target_date, rows=rows)
        db.commit()
        return {"status": "ok", "written": written, "error": None}
    except BirdAuthError as e:
        return {"status": "error", "written": 0, "error": str(e)[:500]}
    except Exception as e:
        logger.exception("Following branch unexpected error")
        return {"status": "error", "written": 0, "error": str(e)[:500]}
