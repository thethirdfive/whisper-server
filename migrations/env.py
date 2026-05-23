"""Alembic 环境配置 - 读 DATABASE_URL，挂载 SQLAlchemy 元数据"""
from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

# 从 env 优先（容器场景），fallback 到 alembic.ini
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/whisper/db/whisper.db")

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型让 Alembic 看到
from app.models import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """生成 SQL 而不连数据库"""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite 必须，支持 ALTER TABLE
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """正常连库迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
