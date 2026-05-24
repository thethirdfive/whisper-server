"""add chunked/resumable upload state to audio_files

Revision ID: 004
Revises: 003
Create Date: 2026-05-24

分块断点续传：audio_files 记录每个文件的上传状态与已收字节数。
  upload_status  ready=已就绪(旧数据/整文件直传) | uploading=分块上传中
  uploaded_bytes 已写入磁盘的字节数（= 续传偏移）
会议在分块上传期间 status="uploading"，全部就绪后 finalize 才入队。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audio_files",
        sa.Column("upload_status", sa.String(16), nullable=False, server_default="ready"),
    )
    op.add_column(
        "audio_files",
        sa.Column("uploaded_bytes", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    with op.batch_alter_table("audio_files") as batch:
        batch.drop_column("uploaded_bytes")
        batch.drop_column("upload_status")
