"""SQLAlchemy 2.0 声明式基类

所有 ORM 模型继承 Base。建表由 Alembic 迁移负责（migrations/versions/001_initial.py），
这里的元数据主要供 ORM 运行时与 alembic autogenerate 比对使用，
因此列定义需与 001 迁移保持一致。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
