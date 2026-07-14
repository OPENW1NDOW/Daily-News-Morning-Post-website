"""业务日：Asia/Shanghai，每天 08:00 换日（与流水线 target_date 一致）。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
CUTOFF_HOUR = 8


def business_date(now: datetime | None = None) -> date:
    """8 点前算前一天，8 点起算当天（CST）。"""
    now_cst = (now or datetime.now(CST)).astimezone(CST)
    if now_cst.hour < CUTOFF_HOUR:
        return (now_cst - timedelta(days=1)).date()
    return now_cst.date()
