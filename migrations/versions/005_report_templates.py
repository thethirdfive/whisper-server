"""add report queue + per-scenario report templates

Revision ID: 005
Revises: 004
Create Date: 2026-05-24

转录后整理（方案一 MCP + Claude Code）：
  meetings.report_status  none | queued | processing | done | failed
  report_templates        每场景一套整理模板（scenario_id 为空=全局默认）
报告产出复用已有的 deliverables 表（kind=report，file_path=HTML）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("report_status", sa.String(16), nullable=False, server_default="none"),
    )
    op.create_table(
        "report_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scenario_id", sa.Integer, sa.ForeignKey("scenarios.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("instructions", sa.Text, nullable=False),
        sa.Column("updated_by", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scenario_id", name="uq_report_templates_scenario"),
    )


def downgrade() -> None:
    op.drop_table("report_templates")
    with op.batch_alter_table("meetings") as batch:
        batch.drop_column("report_status")
