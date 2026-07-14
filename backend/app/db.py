from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401 — 触发模型注册
    Base.metadata.create_all(bind=engine)
    # 安全添加新列（已有则跳过）
    import sqlalchemy as sa
    with engine.connect() as conn:
        for stmt in (
            "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0",
            "ALTER TABLE favorites ADD COLUMN user_id INTEGER",
        ):
            try:
                conn.execute(sa.text(stmt))
                conn.commit()
            except Exception:
                pass  # 列已存在
