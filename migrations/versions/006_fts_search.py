"""switch transcript FTS to trigram tokenizer (Chinese-capable)

Revision ID: 006
Revises: 005
Create Date: 2026-05-24

001 建的 segments_fts 用 unicode61 分词器 —— 它把一整段中文当成一个 token，
无法做中文子串检索。这里替换成 trigram 分词器（按 3 字切，支持中文子串 + bm25 排序 +
snippet 高亮）。仍是 content='segments' 外部内容表，触发器同步；rebuild 回填存量。
查询 ≥3 字走 FTS，更短的由应用层 LIKE 兜底。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _build(tokenize: str, cols: str, trig_cols: str, trig_vals_new: str, trig_vals_old: str) -> None:
    op.execute("DROP TRIGGER IF EXISTS segments_ai")
    op.execute("DROP TRIGGER IF EXISTS segments_ad")
    op.execute("DROP TRIGGER IF EXISTS segments_au")
    op.execute("DROP TABLE IF EXISTS segments_fts")
    op.execute(
        f"CREATE VIRTUAL TABLE segments_fts USING fts5("
        f"{cols}, content='segments', content_rowid='id', tokenize='{tokenize}')"
    )
    op.execute(
        f"CREATE TRIGGER segments_ai AFTER INSERT ON segments BEGIN"
        f"  INSERT INTO segments_fts(rowid, {trig_cols}) VALUES ({trig_vals_new}); END"
    )
    op.execute(
        f"CREATE TRIGGER segments_ad AFTER DELETE ON segments BEGIN"
        f"  INSERT INTO segments_fts(segments_fts, rowid, {trig_cols}) VALUES('delete', {trig_vals_old}); END"
    )
    op.execute(
        f"CREATE TRIGGER segments_au AFTER UPDATE ON segments BEGIN"
        f"  INSERT INTO segments_fts(segments_fts, rowid, {trig_cols}) VALUES('delete', {trig_vals_old});"
        f"  INSERT INTO segments_fts(rowid, {trig_cols}) VALUES ({trig_vals_new}); END"
    )
    op.execute("INSERT INTO segments_fts(segments_fts) VALUES('rebuild')")


def upgrade() -> None:
    # trigram：只索引 text 列即可
    _build("trigram", "text", "text", "new.id, new.text", "old.id, old.text")


def downgrade() -> None:
    # 还原 001 的 unicode61 版本（text + text_normalized）
    _build(
        "unicode61", "text, text_normalized", "text, text_normalized",
        "new.id, new.text, new.text_normalized", "old.id, old.text, old.text_normalized",
    )
