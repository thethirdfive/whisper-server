"""initial schema - all 14 tables

Revision ID: 001
Revises:
Create Date: 2026-05-23

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(128)),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="viewer"),
        sa.Column("locale", sa.String(8), nullable=False, server_default="zh-CN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # ---------- api_tokens ----------
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("token_prefix", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False, server_default="mcp:full"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"])

    # ---------- settings ----------
    op.create_table(
        "settings",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("description", sa.Text),
        sa.Column("is_sensitive", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    # ---------- scenarios ----------
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name_zh", sa.String(128), nullable=False),
        sa.Column("name_en", sa.String(128), nullable=False),
        sa.Column("description_zh", sa.Text),
        sa.Column("description_en", sa.Text),
        sa.Column("icon", sa.String(32)),
        sa.Column("default_template", sa.String(64)),
        sa.Column("builtin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_scenarios_code"),
    )
    op.create_index("ix_scenarios_code", "scenarios", ["code"])

    # ---------- vocabularies ----------
    op.create_table(
        "vocabularies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name_zh", sa.String(128), nullable=False),
        sa.Column("name_en", sa.String(128), nullable=False),
        sa.Column("description_zh", sa.Text),
        sa.Column("description_en", sa.Text),
        sa.Column("industry", sa.String(64)),
        sa.Column("builtin", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_vocabularies_code"),
    )
    op.create_index("ix_vocabularies_code", "vocabularies", ["code"])
    op.create_index("ix_vocabularies_industry", "vocabularies", ["industry"])

    # ---------- vocabulary_terms ----------
    op.create_table(
        "vocabulary_terms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "vocabulary_id",
            sa.Integer,
            sa.ForeignKey("vocabularies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("term_zh", sa.String(256)),
        sa.Column("term_en", sa.String(256)),
        sa.Column("pinyin", sa.String(256)),
        sa.Column("aliases", sa.Text),
        sa.Column("note", sa.Text),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="100"),
    )
    op.create_index("ix_vocabulary_terms_vocab", "vocabulary_terms", ["vocabulary_id"])

    # ---------- scenario_vocabularies ----------
    op.create_table(
        "scenario_vocabularies",
        sa.Column(
            "scenario_id",
            sa.Integer,
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "vocabulary_id",
            sa.Integer,
            sa.ForeignKey("vocabularies.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # ---------- meetings ----------
    op.create_table(
        "meetings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("scenario_id", sa.Integer, sa.ForeignKey("scenarios.id")),
        sa.Column("company", sa.String(128)),
        sa.Column("tags", sa.Text),
        sa.Column("held_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_sec", sa.Integer),
        sa.Column("language", sa.String(8), nullable=False, server_default="zh"),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("custom_prompt", sa.Text),
        sa.Column("owner_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_meetings_scenario_id", "meetings", ["scenario_id"])
    op.create_index("ix_meetings_company", "meetings", ["company"])
    op.create_index("ix_meetings_held_at", "meetings", ["held_at"])
    op.create_index("ix_meetings_held_at_desc", "meetings", ["held_at"])

    # ---------- audio_files ----------
    op.create_table(
        "audio_files",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Integer,
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("original_name", sa.String(512), nullable=False),
        sa.Column("media_kind", sa.String(16), nullable=False, server_default="audio"),
        sa.Column("extracted_audio_path", sa.Text),
        sa.Column("size_bytes", sa.Integer),
        sa.Column("duration_sec", sa.Integer),
        sa.Column("channels", sa.Integer),
        sa.Column("sample_rate", sa.Integer),
        sa.Column("sequence", sa.Integer, nullable=False, server_default="0"),
        sa.Column("included", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(32), nullable=False, server_default="upload"),
        sa.Column("source_ref", sa.Text),
        sa.Column("drive_file_id", sa.String(128)),
        sa.Column("sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audio_files_meeting_id", "audio_files", ["meeting_id"])

    # ---------- speakers ----------
    op.create_table(
        "speakers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Integer,
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128)),
        sa.Column("is_renamed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("meeting_id", "label", name="uq_speakers_meeting_label"),
    )
    op.create_index("ix_speakers_meeting_id", "speakers", ["meeting_id"])

    # ---------- segments ----------
    op.create_table(
        "segments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Integer,
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("speaker_id", sa.Integer, sa.ForeignKey("speakers.id")),
        sa.Column("start_sec", sa.Float, nullable=False),
        sa.Column("end_sec", sa.Float, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("text_normalized", sa.Text),
        sa.Column("confidence", sa.Float),
        sa.Column("sequence", sa.Integer, nullable=False),
    )
    op.create_index("ix_segments_meeting_seq", "segments", ["meeting_id", "sequence"])

    # ---------- FTS5 虚拟表 + 触发器 ----------
    # 注意：alembic autogenerate 不支持 FTS5，必须 raw SQL
    op.execute(
        """
        CREATE VIRTUAL TABLE segments_fts USING fts5(
            text,
            text_normalized,
            content='segments',
            content_rowid='id',
            tokenize='unicode61'
        );
        """
    )
    op.execute(
        """
        CREATE TRIGGER segments_ai AFTER INSERT ON segments BEGIN
            INSERT INTO segments_fts(rowid, text, text_normalized)
            VALUES (new.id, new.text, new.text_normalized);
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER segments_ad AFTER DELETE ON segments BEGIN
            INSERT INTO segments_fts(segments_fts, rowid, text, text_normalized)
            VALUES('delete', old.id, old.text, old.text_normalized);
        END;
        """
    )
    op.execute(
        """
        CREATE TRIGGER segments_au AFTER UPDATE ON segments BEGIN
            INSERT INTO segments_fts(segments_fts, rowid, text, text_normalized)
            VALUES('delete', old.id, old.text, old.text_normalized);
            INSERT INTO segments_fts(rowid, text, text_normalized)
            VALUES (new.id, new.text, new.text_normalized);
        END;
        """
    )

    # ---------- action_items ----------
    op.create_table(
        "action_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Integer,
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("owner_name", sa.String(128)),
        sa.Column("due_date", sa.String(32)),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("source_segment_ids", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_action_items_status_due", "action_items", ["status", "due_date"])

    # ---------- deliverables ----------
    op.create_table(
        "deliverables",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Integer,
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("drive_file_id", sa.String(128)),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ---------- jobs ----------
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("rq_id", sa.String(64)),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("meeting_id", sa.Integer, sa.ForeignKey("meetings.id")),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("message", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("rq_id", name="uq_jobs_rq_id"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_meeting_status", "jobs", ["meeting_id", "status"])

    # ---------- audit_log ----------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32)),
        sa.Column("target_id", sa.Integer),
        sa.Column("metadata", sa.Text),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # ---------- 默认 settings ----------
    op.execute(
        """
        INSERT OR IGNORE INTO settings (key, value, description) VALUES
        ('ui.default_locale', '"zh-CN"', '默认界面语言'),
        ('transcription.model', '"large-v3"', 'Whisper 模型'),
        ('transcription.compute_type', '"int8"', 'WhisperX 计算精度'),
        ('transcription.long_split_threshold_min', '90', '长会议自动分段阈值（分钟）'),
        ('upload.max_size_mb', '4096', '单文件最大尺寸 MB'),
        ('watch_folder.enabled', 'false', 'Watch folder 启用开关'),
        ('watch_folder.scan_interval_sec', '60', 'Watch folder 扫描间隔'),
        ('backup.retention_days', '30', '备份保留天数');
        """
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", "audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_jobs_meeting_status", "jobs")
    op.drop_index("ix_jobs_status", "jobs")
    op.drop_table("jobs")
    op.drop_table("deliverables")
    op.drop_index("ix_action_items_status_due", "action_items")
    op.drop_table("action_items")
    op.execute("DROP TRIGGER IF EXISTS segments_au;")
    op.execute("DROP TRIGGER IF EXISTS segments_ad;")
    op.execute("DROP TRIGGER IF EXISTS segments_ai;")
    op.execute("DROP TABLE IF EXISTS segments_fts;")
    op.drop_index("ix_segments_meeting_seq", "segments")
    op.drop_table("segments")
    op.drop_index("ix_speakers_meeting_id", "speakers")
    op.drop_table("speakers")
    op.drop_index("ix_audio_files_meeting_id", "audio_files")
    op.drop_table("audio_files")
    op.drop_index("ix_meetings_held_at_desc", "meetings")
    op.drop_index("ix_meetings_held_at", "meetings")
    op.drop_index("ix_meetings_company", "meetings")
    op.drop_index("ix_meetings_scenario_id", "meetings")
    op.drop_table("meetings")
    op.drop_table("scenario_vocabularies")
    op.drop_index("ix_vocabulary_terms_vocab", "vocabulary_terms")
    op.drop_table("vocabulary_terms")
    op.drop_index("ix_vocabularies_industry", "vocabularies")
    op.drop_index("ix_vocabularies_code", "vocabularies")
    op.drop_table("vocabularies")
    op.drop_index("ix_scenarios_code", "scenarios")
    op.drop_table("scenarios")
    op.drop_table("settings")
    op.drop_index("ix_api_tokens_user_id", "api_tokens")
    op.drop_table("api_tokens")
    op.drop_index("ix_users_username", "users")
    op.drop_table("users")
