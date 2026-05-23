"""场景、词库、词条，以及场景↔词库关联"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        UniqueConstraint("code", name="uq_scenarios_code"),
        Index("ix_scenarios_code", "code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    description_zh: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(32))
    default_template: Mapped[str | None] = mapped_column(String(64))
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=func.false())
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    vocabularies: Mapped[list["Vocabulary"]] = relationship(
        secondary="scenario_vocabularies", back_populates="scenarios"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Scenario id={self.id} code={self.code!r}>"


class Vocabulary(Base):
    __tablename__ = "vocabularies"
    __table_args__ = (
        UniqueConstraint("code", name="uq_vocabularies_code"),
        Index("ix_vocabularies_code", "code"),
        Index("ix_vocabularies_industry", "industry"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    description_zh: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(64))
    builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=func.false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    terms: Mapped[list["VocabularyTerm"]] = relationship(
        back_populates="vocabulary",
        cascade="all, delete-orphan",
        order_by="VocabularyTerm.sort_order",
    )
    scenarios: Mapped[list["Scenario"]] = relationship(
        secondary="scenario_vocabularies", back_populates="vocabularies"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vocabulary id={self.id} code={self.code!r}>"


class VocabularyTerm(Base):
    __tablename__ = "vocabulary_terms"
    __table_args__ = (Index("ix_vocabulary_terms_vocab", "vocabulary_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vocabulary_id: Mapped[int] = mapped_column(
        ForeignKey("vocabularies.id", ondelete="CASCADE"), nullable=False
    )
    term_zh: Mapped[str | None] = mapped_column(String(256))
    term_en: Mapped[str | None] = mapped_column(String(256))
    pinyin: Mapped[str | None] = mapped_column(String(256))
    aliases: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")

    vocabulary: Mapped["Vocabulary"] = relationship(back_populates="terms")


class ScenarioVocabulary(Base):
    """场景↔词库 多对多关联表"""

    __tablename__ = "scenario_vocabularies"

    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE"), primary_key=True
    )
    vocabulary_id: Mapped[int] = mapped_column(
        ForeignKey("vocabularies.id", ondelete="CASCADE"), primary_key=True
    )
