"""add per-meeting report_context (整理要求/上下文)

Revision ID: 005
Revises: 004
Create Date: 2026-06-20

报告整理要求/上下文：用户在会议详情页自定义「这场会议报告该怎么整理」
（要求 / 备注 / 特点 / 背景上下文）。与转录用的 custom_prompt 分开，
整理器（Claude Code 经 MCP）生成报告时把它连同场景设定一并喂入。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("meetings", sa.Column("report_context", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch:
        batch.drop_column("report_context")
