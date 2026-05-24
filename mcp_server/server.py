"""whisper-server MCP 服务（stdio）

方案一：Claude Code 经 MCP 连到本系统，定期把"待整理"的会议转成 HTML 报告。
Claude Code 在本机用一个含 app 依赖 + mcp 的 venv 启动它（见 .mcp.json / README）。

工具：
  list_pending_reports()            待整理会议（report_status=queued）
  get_meeting(meeting_id)           元数据 + 场景整理模板 + 转录全文
  claim_report(meeting_id)          标记 processing（开始整理，避免重复）
  submit_report(meeting_id, html)   回收 HTML 报告：落盘 + 记录 + done + Bark
  report_failed(meeting_id, error)  标记失败

直连系统同一个 SQLite（DATABASE_URL，host 上即 /data/whisper/db/whisper.db）。
"""
import os
import sys
from pathlib import Path

# 让脚本无论从哪启动都能 import app.* 并加载到仓库根的 .env
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
os.chdir(_ROOT)

from mcp.server.fastmcp import FastMCP  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Meeting  # noqa: E402
from app.services import reports as reports_svc  # noqa: E402

mcp = FastMCP("whisper-server")


@mcp.tool()
def list_pending_reports() -> list[dict]:
    """列出待整理的会议（report_status=queued），按时间倒序。"""
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Meeting).where(Meeting.report_status == "queued").order_by(Meeting.id.desc())
        ).scalars().all()
        return [
            {
                "meeting_id": m.id,
                "title": m.title,
                "scenario": m.scenario.name_zh if m.scenario else None,
                "company": m.company,
                "held_at": m.held_at.isoformat() if m.held_at else None,
                "language": m.language,
                "duration_sec": m.duration_sec,
            }
            for m in rows
        ]
    finally:
        db.close()


@mcp.tool()
def get_meeting(meeting_id: int) -> dict:
    """取一场会议的元数据、该场景的整理模板、以及带说话人/时间戳的转录全文。"""
    db = SessionLocal()
    try:
        m = db.get(Meeting, meeting_id)
        if not m:
            return {"error": f"meeting {meeting_id} 不存在"}
        return {
            "meeting_id": m.id,
            "title": m.title,
            "scenario": m.scenario.name_zh if m.scenario else None,
            "company": m.company,
            "tags": m.tags,
            "held_at": m.held_at.isoformat() if m.held_at else None,
            "language": m.language,
            "duration_sec": m.duration_sec,
            "report_status": m.report_status,
            "template_instructions": reports_svc.get_template(db, m.scenario_id),
            "transcript": reports_svc.transcript_text(db, m),
        }
    finally:
        db.close()


@mcp.tool()
def claim_report(meeting_id: int) -> dict:
    """开始整理前调用：把 queued 标为 processing，避免重复处理。"""
    db = SessionLocal()
    try:
        m = db.get(Meeting, meeting_id)
        if not m:
            return {"ok": False, "error": "不存在"}
        if m.report_status == "queued":
            m.report_status = "processing"
            db.commit()
        return {"ok": True, "report_status": m.report_status}
    finally:
        db.close()


@mcp.tool()
def submit_report(meeting_id: int, html: str, summary: str = "") -> dict:
    """提交整理好的**完整 HTML 报告**：落盘 outputs/ + 建 deliverable + 置 done + Bark 通知。

    html 应为自包含 HTML 文档（内联 CSS）。summary 是一句话摘要（用于通知/列表）。
    """
    db = SessionLocal()
    try:
        d = reports_svc.submit_report(db, meeting_id, html, summary, created_by="claude-code")
        return {"ok": True, "deliverable_id": d.id, "path": d.file_path}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


@mcp.tool()
def report_failed(meeting_id: int, error: str) -> dict:
    """整理失败时调用，把会议标为 failed。"""
    db = SessionLocal()
    try:
        reports_svc.fail_report(db, meeting_id, error)
        return {"ok": True}
    finally:
        db.close()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
