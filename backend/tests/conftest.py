"""
共享测试夹具：内存 SQLite + TestClient，不影响真实数据。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.models import NewsItem, Favorite, Source, RawArticle

# 内存数据库 — StaticPool 确保所有连接共享同一个 :memory: 实例
TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _setup_db():
    """每个测试前重建表结构。"""
    Base.metadata.create_all(bind=_test_engine)
    yield
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def db():
    """返回一个独立的测试数据库 session。"""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(monkeypatch):
    """FastAPI TestClient，覆盖依赖为内存数据库，跳过调度器。"""
    # 阻止调度器启停（测试不需要）
    monkeypatch.setattr("app.main.start_scheduler", lambda: None)
    monkeypatch.setattr("app.main.stop_scheduler", lambda: None)
    # 阻止 lifespan 中对真实数据库的操作
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.sync_sources", lambda db: None)

    from app.main import app
    app.dependency_overrides[get_db] = _override_get_db

    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------- 测试数据构造辅助 ----------

@pytest.fixture
def make_news(db):
    """工厂 fixture：在测试 DB 中插入一条 NewsItem 并返回。"""
    from datetime import date as date_type

    def _make(**kw):
        defaults = {
            "date": date_type(2026, 5, 9),
            "category": "ai",
            "importance": 70,
            "title": "测试标题",
            "summary": "一句话摘要",
            "full_summary": "详细总结内容",
            "viewpoints": [{"view": "某专家认为...", "source": "某媒体"}],
            "background": "背景信息",
            "source_links": [{"name": "来源A", "url": "https://example.com/a"}],
        }
        defaults.update(kw)
        # 自动转换字符串日期
        if isinstance(defaults["date"], str):
            defaults["date"] = date_type.fromisoformat(defaults["date"])
        item = NewsItem(**defaults)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    return _make
