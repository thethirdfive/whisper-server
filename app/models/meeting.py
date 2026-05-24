"""会议及其衍生数据：音频文件、说话人、转录片段、行动项、产物、任务"""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
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


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (
        Index("ix_meetings_scenario_id", "scenario_id"),
        Index("ix_meetings_company", "company"),
        Index("ix_meetings_held_at", "held_at"),
        Index("ix_meetings_held_at_desc", "held_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    scenario_id: Mapped[int | None] = mapped_column(ForeignKey("scenarios.id"))
    company: Mapped[str | None] = mapped_column(String(128))
    tags: Mapped[str | None] = mapped_column(Text)
    held_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(String(8), nullable=False, server_default="zh")
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="uploaded")
    custom_prompt: Mapped[str | None] = mapped_column(Text)
    # 整理报告状态：none=未生成 | queued=待整理 | processing=整理中 | done=已生成 | failed
    report_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="none")
    # 说话人分离：off=不分离 | auto=pyannote 自动估人数 | count=pyannote 指定人数 | channels=按声道拆分
    diarize_mode: Mapped[str] = mapped_column(String(16), nullable=False, server_default="auto")
    num_speakers: Mapped[int | None] = mapped_column(Integer)   # count 模式：确切人数
    min_speakers: Mapped[int | None] = mapped_column(Integer)   # count 模式：最少
    max_speakers: Mapped[int | None] = mapped_column(Integer)   # count 模式：最多
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    scenario: Mapped["Scenario | None"] = relationship("Scenario")  # noqa: F821
    owner: Mapped["User"] = relationship("User")  # noqa: F821
    audio_files: Mapped[list["AudioFile"]] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="AudioFile.sequence",
    )
    speakers: Mapped[list["Speaker"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    segments: Mapped[list["Segment"]] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
        order_by="Segment.sequence",
    )
    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    deliverables: Mapped[list["Deliverable"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Meeting id={self.id} title={self.title!r} status={self.status!r}>"


class AudioFile(Base):
    __tablename__ = "audio_files"
    __table_args__ = (Index("ix_audio_files_meeting_id", "meeting_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    media_kind: Mapped[str] = mapped_column(String(16), nullable=False, server_default="audio")
    extracted_audio_path: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=func.true())
    # 分块上传状态：ready=已就绪(旧数据/直传) | uploading=分块上传中
    upload_status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="ready")
    uploaded_bytes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    source: Mapped[str] = mapped_column(String(32), nullable=False, server_default="upload")
    source_ref: Mapped[str | None] = mapped_column(Text)
    drive_file_id: Mapped[str | None] = mapped_column(String(128))
    sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    meeting: Mapped["Meeting"] = relationship(back_populates="audio_files")


class Speaker(Base):
    __tablename__ = "speakers"
    __table_args__ = (
        UniqueConstraint("meeting_id", "label", name="uq_speakers_meeting_label"),
        Index("ix_speakers_meeting_id", "meeting_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    is_renamed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=func.false()
    )

    meeting: Mapped["Meeting"] = relationship(back_populates="speakers")
    segments: Mapped[list["Segment"]] = relationship(back_populates="speaker")


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (Index("ix_segments_meeting_seq", "meeting_id", "sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    speaker_id: Mapped[int | None] = mapped_column(ForeignKey("speakers.id"))
    start_sec: Mapped[float] = mapped_column(Float, nullable=False)
    end_sec: Mapped[float] = mapped_column(Float, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_normalized: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    meeting: Mapped["Meeting"] = relationship(back_populates="segments")
    speaker: Mapped["Speaker | None"] = relationship(back_populates="segments")


class ActionItem(Base):
    __tablename__ = "action_items"
    __table_args__ = (Index("ix_action_items_status_due", "status", "due_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(128))
    due_date: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="open")
    source_segment_ids: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    meeting: Mapped["Meeting"] = relationship(back_populates="action_items")


class Deliverable(Base):
    __tablename__ = "deliverables"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    drive_file_id: Mapped[str | None] = mapped_column(String(128))
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    meeting: Mapped["Meeting"] = relationship(back_populates="deliverables")


class ReportTemplate(Base):
    """整理模板：每个场景一套（scenario_id 为空 = 全局默认）。

    instructions 是给整理器（Claude Code / LLM）的指令，描述这个场景的报告该怎么写、
    输出 HTML 的结构与重点。整理器读会议全文 + 本模板 → 产出 HTML 报告。
    """
    __tablename__ = "report_templates"
    __table_args__ = (
        UniqueConstraint("scenario_id", name="uq_report_templates_scenario"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int | None] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    scenario: Mapped["Scenario | None"] = relationship("Scenario")  # noqa: F821


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("rq_id", name="uq_jobs_rq_id"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_meeting_status", "meeting_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rq_id: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    meeting_id: Mapped[int | None] = mapped_column(ForeignKey("meetings.id"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="queued")
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    message: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
