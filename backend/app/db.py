from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings
from .utils.logger import get_logger

logger = get_logger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")
    dbapi_conn.execute("PRAGMA busy_timeout=5000")


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
            except Exception as e:
                # 回滚使连接脱离失效事务，否则后续语句抛 PendingRollbackError
                conn.rollback()
                if "duplicate column" in str(e).lower():
                    continue  # 列已存在，预期内
                logger.error(f"启动迁移语句执行失败（不中断启动）: {stmt} -> {e}")
