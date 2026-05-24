"""根据会议场景关联的词库，拼出 Whisper 的 initial_prompt

被 app（上传时预览）与 worker（转录时）共用。规则：
  1. 取会议 scenario 关联的所有词库的词条（中 + 英），去重、按 sort_order
  2. 截断到 settings.whisper_max_prompt_terms 个
  3. 末尾拼接会议自定义 prompt（meeting.custom_prompt）
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Meeting, ScenarioVocabulary, VocabularyTerm
from app.services import settings_store


def scenario_terms(db: Session, scenario_id: int, limit: int) -> list[str]:
    rows = db.execute(
        select(VocabularyTerm)
        .join(
            ScenarioVocabulary,
            ScenarioVocabulary.vocabulary_id == VocabularyTerm.vocabulary_id,
        )
        .where(ScenarioVocabulary.scenario_id == scenario_id)
        .order_by(VocabularyTerm.sort_order, VocabularyTerm.id)
    ).scalars().all()

    terms: list[str] = []
    seen: set[str] = set()
    for t in rows:
        for val in (t.term_zh, t.term_en):
            v = (val or "").strip()
            if v and v not in seen:
                seen.add(v)
                terms.append(v)
            if len(terms) >= limit:
                return terms
    return terms


def build_initial_prompt(db: Session, meeting: Meeting, max_terms: int | None = None) -> str:
    limit = max_terms if max_terms is not None else int(
        settings_store.effective(db, "whisper_max_prompt_terms")
    )

    terms: list[str] = []
    if meeting.scenario_id:
        terms = scenario_terms(db, meeting.scenario_id, limit)

    parts: list[str] = []
    if terms:
        parts.append("、".join(terms))
    if meeting.custom_prompt and meeting.custom_prompt.strip():
        parts.append(meeting.custom_prompt.strip())
    return "。".join(parts)
