"""全文搜索：SQLite FTS5 trigram 索引（segments）+ bm25 排序 + snippet 高亮。

- 查询 >=3 字 → 走 FTS5 trigram（支持中文子串、有相关性排序）。
- 查询 <3 字 → trigram 无法成词，退回 LIKE 子串扫描。
- 同时 LIKE 匹配会议标题/公司/标签，结果按会议分组。
高亮用私有区字符作 snippet 标记，HTML 转义后再替换成 <mark>，避免 XSS。
"""
import html as _html

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.models import Meeting, Segment

# snippet 高亮起止标记（私有区字符，转录正文不会出现）
_M1 = chr(0xE000)
_M2 = chr(0xE001)


def _render(raw: str) -> str:
    return _html.escape(raw or "").replace(_M1, "<mark>").replace(_M2, "</mark>")


def _like_snip(txt: str, q: str, ctx: int = 18) -> str:
    i = (txt or "").find(q)
    if i < 0:
        return _html.escape((txt or "")[: 2 * ctx])
    a, b = max(0, i - ctx), min(len(txt), i + len(q) + ctx)
    pre = ("…" if a > 0 else "") + txt[a:i]
    post = txt[i + len(q):b] + ("…" if b < len(txt) else "")
    return _html.escape(pre) + "<mark>" + _html.escape(txt[i:i + len(q)]) + "</mark>" + _html.escape(post)


def _segment_hits(db: Session, q: str, limit: int) -> list[tuple[int, float, str]]:
    if len(q) >= 3:
        sql = text(
            "SELECT s.meeting_id AS mid, s.start_sec AS st, "
            f"  snippet(segments_fts, 0, '{_M1}', '{_M2}', '…', 16) AS snip, "
            "  bm25(segments_fts) AS rank "
            "FROM segments_fts JOIN segments s ON s.id = segments_fts.rowid "
            "WHERE segments_fts MATCH :m ORDER BY rank LIMIT :lim"
        )
        m = '"' + q.replace('"', '""') + '"'
        rows = db.execute(sql, {"m": m, "lim": limit}).mappings().all()
        return [(r["mid"], r["st"], _render(r["snip"])) for r in rows]
    # <3 字：LIKE 兜底
    rows = db.execute(
        select(Segment.meeting_id, Segment.start_sec, Segment.text)
        .where(Segment.text.like(f"%{q}%"))
        .order_by(Segment.meeting_id.desc(), Segment.sequence)
        .limit(limit)
    ).all()
    return [(mid, st, _like_snip(txt, q)) for mid, st, txt in rows]


def search(db: Session, q: str, *, max_meetings: int = 40, per_meeting: int = 4,
           seg_limit: int = 300) -> dict:
    q = (q or "").strip()
    if not q:
        return {"q": "", "groups": [], "total": 0, "mode": None}

    hits = _segment_hits(db, q, seg_limit)
    order: list[int] = []
    groups: dict[int, dict] = {}
    for mid, st, snip in hits:
        g = groups.get(mid)
        if g is None:
            g = groups[mid] = {"hits": [], "n": 0, "title_match": False}
            order.append(mid)
        g["n"] += 1
        if len(g["hits"]) < per_meeting:
            g["hits"].append({"start_sec": st, "snippet": snip})

    # 标题/公司/标签命中（即便正文没命中也纳入）
    like = f"%{q}%"
    title_mids = db.execute(
        select(Meeting.id).where(
            or_(Meeting.title.like(like), Meeting.company.like(like), Meeting.tags.like(like))
        )
    ).scalars().all()
    for mid in title_mids:
        g = groups.get(mid)
        if g is None:
            g = groups[mid] = {"hits": [], "n": 0, "title_match": True}
            order.append(mid)
        else:
            g["title_match"] = True

    order = order[:max_meetings]
    mobjs = {
        m.id: m
        for m in db.execute(select(Meeting).where(Meeting.id.in_(order))).scalars().all()
    }
    result = [{"meeting": mobjs[mid], **groups[mid]} for mid in order if mid in mobjs]
    return {"q": q, "groups": result, "total": len(hits),
            "mode": "fts" if len(q) >= 3 else "like"}
