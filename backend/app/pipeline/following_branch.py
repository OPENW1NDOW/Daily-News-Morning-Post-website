"""Following 旁路：抓取关注账号推文 → 过滤精选 → upsert news_items。"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
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
    on_progress: Callable[[str], None] | None = None,
) -> dict:
    """
    Following 旁路入口。
    返回 {status: "ok"|"skipped"|"error", written: int, error: str|None}。
    不写入 raw_articles。
    """
    def _progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    try:
        if not (settings.x_auth_token or "").strip() or not (settings.x_ct0 or "").strip():
            _progress("Following 已跳过（未配置 Cookie）")
            return {"status": "skipped", "written": 0, "error": None}

        accounts = _enabled_following(db)
        if not accounts:
            # 仅当表为空时自动 sync；用户禁用全部账号则跳过，不覆盖
            if db.query(XAccount).count() == 0:
                try:
                    _progress("正在同步 X 关注列表…")
                    sync_following_accounts(db)
                    db.commit()
                except Exception as e:
                    logger.exception("Following sync failed")
                    return {"status": "error", "written": 0, "error": str(e)[:500]}
                accounts = _enabled_following(db)
            if not accounts:
                _progress("Following 已跳过（无启用账号）")
                return {"status": "skipped", "written": 0, "error": None}

        sem = asyncio.Semaphore(_FETCH_CONCURRENCY)
        since_iso = day_start.isoformat()
        until_iso = day_end.isoformat()
        n_accounts = len(accounts)
        done_fetches = 0
        fetch_progress_lock = asyncio.Lock()

        async def _fetch_one(account: XAccount) -> list[dict]:
            nonlocal done_fetches
            async with sem:
                tweets = await asyncio.to_thread(
                    fetch_user_tweets,
                    account.handle,
                    since_iso,
                    until_iso,
                )
                async with fetch_progress_lock:
                    done_fetches += 1
                    current = done_fetches
                _progress(f"正在抓取 X 推文… {current}/{n_accounts}")
                return tweets

        _progress(f"正在抓取 X 推文… 0/{n_accounts}")
        results = await asyncio.gather(
            *[_fetch_one(a) for a in accounts],
            return_exceptions=True,
        )

        all_tweets: list[dict] = []
        ok_fetches = 0
        fail_errors: list[str] = []
        for account, result in zip(accounts, results):
            if isinstance(result, BirdAuthError):
                return {"status": "error", "written": 0, "error": str(result)[:500]}
            if isinstance(result, Exception):
                logger.warning(
                    "fetch tweets failed for @%s: %s",
                    account.handle,
                    result,
                )
                fail_errors.append(f"@{account.handle}: {result}")
                continue
            ok_fetches += 1
            all_tweets.extend(result)

        if accounts and ok_fetches == 0:
            err = "all tweet fetches failed"
            if fail_errors:
                err = f"{err}: {'; '.join(fail_errors)}"
            return {"status": "error", "written": 0, "error": err[:500]}

        filtered = filter_tweets(all_tweets)
        _progress(f"AI 正在精选 Following（候选 {len(filtered)}）…")
        try:
            selected = select_tweets(filtered)[:_FINAL_TOP_N]
        except Exception as e:
            logger.exception("Following select failed")
            return {"status": "error", "written": 0, "error": str(e)[:500]}

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

        # 与 RSS 无候选不 wipe 对齐：软空结果保留当日已有 Following
        if not rows:
            _progress("Following 无候选，跳过写入")
            return {"status": "ok", "written": 0, "error": None}

        _progress("正在写入 Following…")
        written = upsert_following_items(db, target_date=target_date, rows=rows)
        db.commit()
        return {"status": "ok", "written": written, "error": None}
    except BirdAuthError as e:
        return {"status": "error", "written": 0, "error": str(e)[:500]}
    except Exception as e:
        logger.exception("Following branch unexpected error")
        return {"status": "error", "written": 0, "error": str(e)[:500]}
