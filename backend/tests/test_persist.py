from datetime import date
from app.models import NewsItem, Favorite, User
from app.pipeline.persist import upsert_rss_items, upsert_following_items, EXTERNAL_ID_KEY


def test_rss_upsert_keeps_id_and_favorite(db):
    d = date.today()
    item = NewsItem(
        date=d, category="ai", importance=80, title="旧标题",
        summary="旧", raw_article_id=101,
        source_links=[{"name": "源", "url": "https://example.com/a"}],
    )
    db.add(item)
    db.flush()
    user = User(username="u1", password_hash="x")
    db.add(user)
    db.flush()
    db.add(Favorite(user_id=user.id, news_item_id=item.id))
    db.commit()
    old_id = item.id

    written = upsert_rss_items(
        db,
        target_date=d,
        category="ai",
        rows=[
            {
                "raw_article_id": 101,
                "importance": 90,
                "title": "新标题",
                "summary": "新摘要",
                "full_summary": "全文",
                "viewpoints": ["a"],
                "background": "bg",
                "source_links": [{"name": "源", "url": "https://example.com/a"}],
            }
        ],
    )
    db.commit()
    assert written == 1
    again = db.query(NewsItem).filter_by(id=old_id).one()
    assert again.title == "新标题"
    assert again.importance == 90
    assert db.query(Favorite).filter_by(news_item_id=old_id).count() == 1


def test_rss_deletes_unfavorited_absent_from_new_set(db):
    d = date.today()
    keep = NewsItem(date=d, category="ai", importance=80, title="留", raw_article_id=1, source_links=[])
    drop = NewsItem(date=d, category="ai", importance=50, title="丢", raw_article_id=2, source_links=[])
    db.add_all([keep, drop])
    db.commit()

    upsert_rss_items(
        db,
        target_date=d,
        category="ai",
        rows=[{
            "raw_article_id": 1,
            "importance": 80,
            "title": "留",
            "summary": None,
            "full_summary": None,
            "viewpoints": None,
            "background": None,
            "source_links": [],
        }],
    )
    db.commit()
    ids = {n.raw_article_id for n in db.query(NewsItem).filter_by(date=d, category="ai").all()}
    assert ids == {1}


def test_rss_keeps_favorited_even_if_absent_from_new_set(db):
    d = date.today()
    fav_item = NewsItem(date=d, category="ai", importance=50, title="藏", raw_article_id=2, source_links=[])
    db.add(fav_item)
    db.flush()
    user = User(username="u2", password_hash="x")
    db.add(user)
    db.flush()
    db.add(Favorite(user_id=user.id, news_item_id=fav_item.id))
    db.commit()

    upsert_rss_items(db, target_date=d, category="ai", rows=[])
    db.commit()
    assert db.query(NewsItem).filter_by(id=fav_item.id).one().title == "藏"


def test_following_upsert_by_external_id(db):
    d = date.today()
    item = NewsItem(
        date=d, category="following", importance=70, title="旧推",
        raw_article_id=None,
        source_links=[{"name": "@a", "url": "https://x.com/i/status/99", EXTERNAL_ID_KEY: "99"}],
    )
    db.add(item)
    db.commit()
    old_id = item.id

    upsert_following_items(
        db,
        target_date=d,
        rows=[{
            "external_id": "99",
            "importance": 88,
            "title": "新推",
            "summary": "s",
            "full_summary": "s",
            "viewpoints": None,
            "background": None,
            "handle": "a",
            "url": "https://x.com/i/status/99",
        }],
    )
    db.commit()
    again = db.get(NewsItem, old_id)
    assert again.title == "新推"
    assert again.importance == 88
    assert len(again.source_links) == 1
    link = again.source_links[0]
    assert link["name"] == "@a"
    assert link[EXTERNAL_ID_KEY] == "99"
    assert link["url"] == "https://x.com/i/status/99"


def test_following_deletes_unfavorited_absent_from_new_set(db):
    d = date.today()
    keep = NewsItem(
        date=d, category="following", importance=80, title="留",
        raw_article_id=None,
        source_links=[{"name": "@a", "url": "https://x.com/i/status/1", EXTERNAL_ID_KEY: "1"}],
    )
    drop = NewsItem(
        date=d, category="following", importance=50, title="丢",
        raw_article_id=None,
        source_links=[{"name": "@b", "url": "https://x.com/i/status/2", EXTERNAL_ID_KEY: "2"}],
    )
    db.add_all([keep, drop])
    db.commit()

    upsert_following_items(
        db,
        target_date=d,
        rows=[{
            "external_id": "1",
            "importance": 80,
            "title": "留",
            "summary": None,
            "full_summary": None,
            "viewpoints": None,
            "background": None,
            "handle": "a",
            "url": "https://x.com/i/status/1",
        }],
    )
    db.commit()
    items = db.query(NewsItem).filter_by(date=d, category="following").all()
    ids = {n.source_links[0][EXTERNAL_ID_KEY] for n in items}
    assert ids == {"1"}


def test_following_keeps_favorited_even_if_absent_from_new_set(db):
    d = date.today()
    fav_item = NewsItem(
        date=d, category="following", importance=50, title="藏",
        raw_article_id=None,
        source_links=[{"name": "@b", "url": "https://x.com/i/status/2", EXTERNAL_ID_KEY: "2"}],
    )
    db.add(fav_item)
    db.flush()
    user = User(username="u3", password_hash="x")
    db.add(user)
    db.flush()
    db.add(Favorite(user_id=user.id, news_item_id=fav_item.id))
    db.commit()

    upsert_following_items(db, target_date=d, rows=[])
    db.commit()
    assert db.query(NewsItem).filter_by(id=fav_item.id).one().title == "藏"
