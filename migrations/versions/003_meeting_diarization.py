"""add speaker-diarization options to meetings

Revision ID: 003
Revises: 002
Create Date: 2026-05-24

给 meetings 加上每场会议可选的说话人分离配置：
  diarize_mode  off | auto | count | channels（默认 auto，保持原有"有 token 就分离"的行为）
  num/min/max_speakers  count 模式下传给 pyannote 的人数约束
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("diarize_mode", sa.String(16), nullable=False, server_default="auto"),
    )
    op.add_column("meetings", sa.Column("num_speakers", sa.Integer))
    op.add_column("meetings", sa.Column("min_speakers", sa.Integer))
    op.add_column("meetings", sa.Column("max_speakers", sa.Integer))


def downgrade() -> None:
    with op.batch_alter_table("meetings") as batch:
        batch.drop_column("max_speakers")
        batch.drop_column("min_speakers")
        batch.drop_column("num_speakers")
        batch.drop_column("diarize_mode")
