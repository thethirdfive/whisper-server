"""load predefined scenarios + vocabularies + 385 terms

Revision ID: 002
Revises: 001
Create Date: 2026-05-23

读取 /app/seeds/vocabulary_seed.sql 一次性灌入 7 个词库 / 10 个场景 / 385 词条。

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_PATH = Path("/app/seeds/vocabulary_seed.sql")


def upgrade() -> None:
    if not SEED_PATH.exists():
        # 开发环境可能在仓库根目录
        alt_path = Path(__file__).resolve().parents[2] / "seeds" / "vocabulary_seed.sql"
        if alt_path.exists():
            sql = alt_path.read_text(encoding="utf-8")
        else:
            print(f"⚠️ 找不到 seed 文件：{SEED_PATH} 或 {alt_path}，跳过")
            return
    else:
        sql = SEED_PATH.read_text(encoding="utf-8")

    # 拿到底层 sqlite3 connection 用 executescript（最稳，原生处理 ; 分隔）
    # 先去掉 BEGIN/COMMIT（Alembic 已经在事务里）
    sql_clean = "\n".join(
        line for line in sql.splitlines()
        if not line.strip().upper().startswith(("BEGIN TRANSACTION", "COMMIT"))
    )

    conn = op.get_bind()
    raw = conn.connection.connection  # 底层 sqlite3.Connection
    raw.executescript(sql_clean)

    # 验证
    sc = conn.exec_driver_sql("SELECT COUNT(*) FROM scenarios").scalar()
    vc = conn.exec_driver_sql("SELECT COUNT(*) FROM vocabularies").scalar()
    tc = conn.exec_driver_sql("SELECT COUNT(*) FROM vocabulary_terms").scalar()
    print(f"✅ 预置词库已加载：场景 {sc} / 词库 {vc} / 词条 {tc}")


def downgrade() -> None:
    conn = op.get_bind()
    # 清空预置数据（builtin=1）
    conn.exec_driver_sql("DELETE FROM scenario_vocabularies;")
    conn.exec_driver_sql("DELETE FROM vocabulary_terms WHERE vocabulary_id IN (SELECT id FROM vocabularies WHERE builtin = 1);")
    conn.exec_driver_sql("DELETE FROM vocabularies WHERE builtin = 1;")
    conn.exec_driver_sql("DELETE FROM scenarios WHERE builtin = 1;")
