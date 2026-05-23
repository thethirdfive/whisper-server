"""SQLAlchemy engine + session 工厂"""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# 连接 SQLite 时启用 foreign key + WAL
def _make_engine() -> Engine:
    eng = create_engine(
        settings.database_url,
        echo=(settings.app_env == "development" and settings.log_level == "DEBUG"),
        future=True,
        connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    )

    if "sqlite" in settings.database_url:
        @event.listens_for(eng, "connect")
        def _set_sqlite_pragmas(dbapi_conn, _conn_record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys = ON")
            cur.execute("PRAGMA journal_mode = WAL")
            cur.execute("PRAGMA synchronous = NORMAL")
            cur.execute("PRAGMA temp_store = MEMORY")
            cur.execute("PRAGMA mmap_size = 268435456")  # 256MB
            cur.close()

    return eng


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用的 session 生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
