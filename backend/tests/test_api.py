"""
API 冒烟测试：覆盖 health / categories / news / favorites / admin 全部端点。
"""
from datetime import date


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


class TestCategories:
    def test_returns_categories(self, client):
        resp = client.get("/api/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 8
        keys = {c["key"] for c in data}
        assert "ai" in keys
        assert "tech" in keys
        for c in data:
            assert c["count"] == 0

    def test_counts_reflect_today_items(self, client, make_news):
        make_news(category="ai", date=date.today().isoformat())
        make_news(category="ai", date=date.today().isoformat())
        make_news(category="tech", date=date.today().isoformat())

        resp = client.get("/api/categories")
        data = resp.json()
        by_key = {c["key"]: c["count"] for c in data}
        assert by_key["ai"] == 2
        assert by_key["tech"] == 1
        assert by_key["international"] == 0


class TestNewsList:
    def test_empty_by_default(self, client):
        resp = client.get("/api/news")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_today_items(self, client, make_news):
        make_news(category="ai", title="AI News", date=date.today().isoformat())
        make_news(category="ai", title="AI News 2", date=date.today().isoformat())

        resp = client.get("/api/news")
        data = resp.json()
        assert len(data) == 2
        assert data[0]["title"] == "AI News"
        assert data[0]["is_favorited"] is False

    def test_filter_by_category(self, client, make_news):
        make_news(category="ai", title="AI", date=date.today().isoformat())
        make_news(category="tech", title="Tech", date=date.today().isoformat())

        resp = client.get("/api/news?category=tech")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Tech"

    def test_filter_by_date(self, client, make_news):
        make_news(category="ai", title="Today", date=date.today().isoformat())
        make_news(category="ai", title="Yesterday", date="2026-05-08")

        resp = client.get("/api/news?date=2026-05-08")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "Yesterday"

    def test_limit_6_per_category(self, client, make_news):
        for i in range(8):
            make_news(category="ai", title=f"News {i}", importance=80 - i, date=date.today().isoformat())

        resp = client.get("/api/news?category=ai")
        data = resp.json()
        assert len(data) == 6

    def test_marks_favorited(self, client, make_news):
        item = make_news(category="ai", date=date.today().isoformat())
        client.post("/api/favorites", json={"news_item_id": item.id})

        resp = client.get("/api/news")
        data = resp.json()
        assert data[0]["is_favorited"] is True


class TestNewsDetail:
    def test_returns_full_detail(self, client, make_news):
        item = make_news(category="ai", title="Detail Test", date=date.today().isoformat())

        resp = client.get(f"/api/news/{item.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Detail Test"
        assert data["full_summary"] == "详细总结内容"
        assert len(data["viewpoints"]) == 1
        assert len(data["source_links"]) == 1
        assert data["is_favorited"] is False

    def test_404_for_missing(self, client):
        resp = client.get("/api/news/99999")
        assert resp.status_code == 404


class TestFavorites:
    def test_add_favorite(self, client, make_news):
        item = make_news(date=date.today().isoformat())

        resp = client.post("/api/favorites", json={"news_item_id": item.id})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    def test_add_duplicate_returns_existing(self, client, make_news):
        item = make_news(date=date.today().isoformat())
        client.post("/api/favorites", json={"news_item_id": item.id})
        resp = client.post("/api/favorites", json={"news_item_id": item.id})
        assert resp.status_code == 200

    def test_add_nonexistent_news_returns_404(self, client):
        resp = client.post("/api/favorites", json={"news_item_id": 99999})
        assert resp.status_code == 404

    def test_remove_favorite(self, client, make_news):
        item = make_news(date=date.today().isoformat())
        client.post("/api/favorites", json={"news_item_id": item.id})

        resp = client.delete(f"/api/favorites/{item.id}")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_remove_nonexistent_returns_404(self, client):
        resp = client.delete("/api/favorites/99999")
        assert resp.status_code == 404

    def test_list_favorites(self, client, make_news):
        item = make_news(date=date.today().isoformat())
        client.post("/api/favorites", json={"news_item_id": item.id})

        resp = client.get("/api/favorites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["is_favorited"] is True

    def test_list_empty(self, client):
        resp = client.get("/api/favorites")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestAdmin:
    def test_status_returns_info(self, client):
        resp = client.get("/api/admin/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "today_count" in data
        assert "pipeline_running" in data
        assert "last_run" in data
        assert "sources" in data

    def test_refresh_returns_started(self, client, monkeypatch):
        # mock 后台任务，避免实际执行流水线
        monkeypatch.setattr("app.api.admin._run_pipeline_sync", lambda *a: None)
        resp = client.post("/api/admin/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("started", "already_running")
