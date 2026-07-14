from datetime import date, datetime, timedelta, timezone

from app.utils.timeutil import CST, CUTOFF_HOUR, business_date


def test_business_date_before_cutoff_is_previous_day():
    now = datetime(2026, 7, 14, 1, 30, tzinfo=CST)
    assert business_date(now) == date(2026, 7, 13)


def test_business_date_at_and_after_cutoff_is_same_day():
    assert business_date(datetime(2026, 7, 14, CUTOFF_HOUR, 0, tzinfo=CST)) == date(2026, 7, 14)
    assert business_date(datetime(2026, 7, 14, 12, 0, tzinfo=CST)) == date(2026, 7, 14)


def test_admin_status_today_count_uses_business_date(client, make_news, monkeypatch):
    """8 点前写入「昨天」后，today_count 应计入业务日，避免首页空数据循环 refresh。"""
    from app.api import admin as admin_mod
    from app.utils import timeutil

    biz = date(2026, 7, 13)
    monkeypatch.setattr(timeutil, "business_date", lambda now=None: biz)
    monkeypatch.setattr(admin_mod, "business_date", lambda now=None: biz)

    make_news(category="ai", date=biz.isoformat())
    make_news(category="tech", date=biz.isoformat())
    # 日历「今天」有数据也不该干扰业务日统计以外的断言；此处确保 status 读的是 biz
    make_news(category="ai", date="2026-07-14")

    resp = client.get("/api/admin/status")
    assert resp.status_code == 200
    assert resp.json()["today_count"] == 2
