"""ORM 模型聚合导出

建表由 Alembic 迁移负责；此处定义供 ORM 运行时使用，且 migrations/env.py 通过
Base.metadata 给 alembic autogenerate 比对。新增表时记得在这里 re-export。
"""
from app.models.base import Base
from app.models.meeting import (
    ActionItem,
    AudioFile,
    Deliverable,
    Job,
    Meeting,
    Segment,
    Speaker,
)
from app.models.setting import Setting
from app.models.user import ApiToken, AuditLog, User
from app.models.vocabulary import (
    Scenario,
    ScenarioVocabulary,
    Vocabulary,
    VocabularyTerm,
)

__all__ = [
    "Base",
    "User",
    "ApiToken",
    "AuditLog",
    "Setting",
    "Scenario",
    "ScenarioVocabulary",
    "Vocabulary",
    "VocabularyTerm",
    "Meeting",
    "AudioFile",
    "Speaker",
    "Segment",
    "ActionItem",
    "Deliverable",
    "Job",
]
