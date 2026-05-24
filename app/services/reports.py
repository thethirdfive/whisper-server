"""转录后整理：整理队列 + 场景模板 + 提交 HTML 报告。

整理器（方案一：Claude Code 经 MCP；方案二：LLM API worker）共用本模块：
  - get_template()      取该场景的整理模板（场景级 → 全局 → 内置默认）
  - transcript_text()   把会议转录拼成带说话人/时间戳的纯文本喂给整理器
  - queue_report()      把会议标记为待整理（report_status=queued）
  - submit_report()     回收 HTML 报告：落盘 + 建 deliverable + 置 done + Bark 通知
"""
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Deliverable, Meeting, ReportTemplate, Segment, Speaker
from app.services import notify, settings_store

log = structlog.get_logger()

# 内置默认模板（场景没单独配时用）。整理器据此产出自包含 HTML 报告。
DEFAULT_TEMPLATE = """\
你是会议记录整理助手。根据下方会议转录全文，生成一份**结构清晰、表现力强的自包含 HTML 报告**。

要求：
- 输出**完整的 HTML 文档**（含 <html><head><style>…</style></head><body>…），内联 CSS，可直接在浏览器打开；中文，排版美观、专业。
- 建议包含：会议概要 / 关键议题与结论 / 决策事项 / 待办行动项（负责人·截止时间，如有）/ 风险与跟进 / 按主题或说话人的要点。
- 善用标题层级、表格、列表、要点高亮、必要时用简单图示，**体现要点之间的关联**。
- 忠于原文、不杜撰；信息不足处标注“未提及”。
- 只输出 HTML 本身，不要额外解释或代码块围栏。"""


def get_template(db: Session, scenario_id: int | None) -> str:
    """场景级模板 → 全局模板(scenario_id 为空) → 内置默认。"""
    row = None
    if scenario_id:
        row = db.execute(
            select(ReportTemplate).where(ReportTemplate.scenario_id == scenario_id)
        ).scalar_one_or_none()
    if row is None:
        row = db.execute(
            select(ReportTemplate).where(ReportTemplate.scenario_id.is_(None))
        ).scalar_one_or_none()
    return row.instructions if row else DEFAULT_TEMPLATE


def transcript_text(db: Session, meeting: Meeting) -> str:
    """拼成 `[mm:ss] 说话人: 文本` 的纯文本。"""
    speakers = {
        s.id: (s.display_name or s.label)
        for s in db.execute(select(Speaker).where(Speaker.meeting_id == meeting.id)).scalars().all()
    }
    segs = db.execute(
        select(Segment).where(Segment.meeting_id == meeting.id).order_by(Segment.sequence)
    ).scalars().all()
    lines = []
    for s in segs:
        mm, ss = divmod(int(s.start_sec or 0), 60)
        who = speakers.get(s.speaker_id, "")
        prefix = f"[{mm:02d}:{ss:02d}]" + (f" {who}: " if who else " ")
        lines.append(prefix + (s.text or "").strip())
    return "\n".join(lines)


def queue_report(db: Session, meeting: Meeting) -> None:
    meeting.report_status = "queued"
    db.commit()
    log.info("report_queued", meeting_id=meeting.id)


def submit_report(
    db: Session,
    meeting_id: int,
    html: str,
    summary: str = "",
    created_by: str = "claude-code",
) -> Deliverable:
    """整理器回收 HTML 报告：落盘 outputs/{id}/ + 建 deliverable + done + Bark。"""
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise ValueError(f"meeting {meeting_id} 不存在")

    settings = get_settings()
    out_dir = Path(settings.data_root) / "outputs" / str(meeting_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"report_{ts}.html"
    path.write_text(html, encoding="utf-8")

    d = Deliverable(
        meeting_id=meeting_id, kind="report", file_path=str(path),
        created_by=created_by, note=(summary or "")[:2000],
    )
    db.add(d)
    meeting.report_status = "done"
    db.commit()
    db.refresh(d)
    log.info("report_submitted", meeting_id=meeting_id, deliverable_id=d.id, path=str(path))

    notify.bark(
        f"📋 报告已生成：{meeting.title}",
        summary or "会议整理完成，可在系统查看。",
        key=settings_store.effective(db, "bark_key"),
    )
    return d


def fail_report(db: Session, meeting_id: int, error: str) -> None:
    meeting = db.get(Meeting, meeting_id)
    if meeting:
        meeting.report_status = "failed"
        db.commit()
    log.warning("report_failed", meeting_id=meeting_id, error=error[:300])
