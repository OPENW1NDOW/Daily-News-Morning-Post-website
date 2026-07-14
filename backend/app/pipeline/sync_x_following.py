"""Sync X following list into x_accounts with upsert / unfollow semantics."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import XAccount
from .bird_client import list_following


def sync_following_accounts(db: Session) -> None:
    # Fetch first — if this raises, leave DB untouched.
    accounts = [
        a for a in list_following()
        if str(a.get("x_user_id") or "").strip() and str(a.get("handle") or "").strip()
    ]
    now = datetime.now(timezone.utc)
    fetched_ids = {a["x_user_id"] for a in accounts}

    existing = {
        row.x_user_id: row
        for row in db.query(XAccount).all()
    }

    for item in accounts:
        x_user_id = item["x_user_id"]
        row = existing.get(x_user_id)
        if row is None:
            db.add(
                XAccount(
                    x_user_id=x_user_id,
                    handle=item["handle"],
                    display_name=item.get("display_name") or "",
                    avatar_url=item.get("avatar_url"),
                    enabled=True,
                    is_following=True,
                    last_synced_at=now,
                )
            )
        else:
            row.handle = item["handle"]
            row.display_name = item.get("display_name") or ""
            row.avatar_url = item.get("avatar_url")
            row.is_following = True
            row.last_synced_at = now
            # Never overwrite enabled

    for x_user_id, row in existing.items():
        if x_user_id not in fetched_ids:
            row.is_following = False

    db.flush()
