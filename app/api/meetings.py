"""会议列表 / 上传向导 / 详情 / 状态轮询"""
import shutil
from datetime import datetime
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.config import get_settings
from app.database import get_db
from app.models import AudioFile, Job, Meeting, Scenario, Segment, Speaker, User
from app.services import queue as queue_svc
from app.services import storage
from app.services.prompt import build_initial_prompt
from app.templating import templates

router = APIRouter(prefix="/meetings", tags=["meetings"])
log = structlog.get_logger()
settings = get_settings()

CHUNK = 1024 * 1024
TERMINAL = {"transcribed", "failed"}


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _parse_held_at(raw: str) -> datetime:
    raw = (raw or "").strip()
    if not raw:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow()


def _latest_job(db: Session, meeting_id: int) -> Job | None:
    return db.execute(
        select(Job).where(Job.meeting_id == meeting_id).order_by(desc(Job.id)).limit(1)
    ).scalar_one_or_none()


@router.get("", response_class=HTMLResponse)
def list_meetings(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    msg: str | None = None,
    error: str | None = None,
):
    meetings = db.execute(select(Meeting).order_by(desc(Meeting.held_at))).scalars().all()
    return templates.TemplateResponse(
        request,
        "meetings/list.html",
        {"user": user, "meetings": meetings, "msg": msg, "error": error},
    )


@router.get("/new", response_class=HTMLResponse)
def new_meeting(
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    error: str | None = None,
):
    scenarios = db.execute(select(Scenario).order_by(Scenario.sort_order, Scenario.id)).scalars().all()
    return templates.TemplateResponse(
        request,
        "meetings/new.html",
        {
            "user": user,
            "scenarios": scenarios,
            "error": error,
            "allowed_audio": sorted(settings.allowed_audio_set),
            "allowed_video": sorted(settings.allowed_video_set),
            "max_size_mb": settings.upload_max_size_mb,
        },
    )


@router.post("")
async def create_meeting(
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    title: str = Form(...),
    scenario_id: str = Form(""),
    company: str = Form(""),
    held_at: str = Form(""),
    language: str = Form("zh"),
    tags: str = Form(""),
    custom_prompt: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    title = title.strip()
    files = [f for f in files if f and f.filename]
    if not title:
        return _redirect("/meetings/new?error=请填写会议标题")
    if not files:
        return _redirect("/meetings/new?error=请至少选择一个音频或视频文件")

    # 扩展名校验（保存前）
    allowed = settings.allowed_extensions
    for f in files:
        ext = Path(f.filename).suffix.lower().lstrip(".")
        if ext not in allowed:
            return _redirect(f"/meetings/new?error=不支持的文件类型：.{ext}")

    sid = int(scenario_id) if scenario_id.strip().isdigit() else None

    meeting = Meeting(
        title=title,
        scenario_id=sid,
        company=company.strip() or None,
        tags=tags.strip() or None,
        held_at=_parse_held_at(held_at),
        language=(language.strip() or "zh")[:8],
        status="uploaded",
        custom_prompt=custom_prompt.strip() or None,
        owner_id=user.id,
    )
    db.add(meeting)
    db.flush()  # 拿到 meeting.id 但还没提交

    budget = settings.upload_max_size_mb * 1024 * 1024
    used = 0
    dest_dir = storage.meeting_recordings_dir(meeting.id)
    try:
        for seq, up in enumerate(files):
            ext = Path(up.filename).suffix.lower().lstrip(".")
            safe = storage.safe_filename(up.filename)
            dest = dest_dir / f"{seq:02d}_{safe}"
            size = 0
            with dest.open("wb") as out:
                while True:
                    chunk = await up.read(CHUNK)
                    if not chunk:
                        break
                    used += len(chunk)
                    if used > budget:
                        raise ValueError("over_budget")
                    size += len(chunk)
                    out.write(chunk)
            db.add(
                AudioFile(
                    meeting_id=meeting.id,
                    file_path=str(dest),
                    original_name=up.filename,
                    media_kind="video" if ext in settings.allowed_video_set else "audio",
                    size_bytes=size,
                    sequence=seq,
                    source="upload",
                )
            )
    except ValueError:
        db.rollback()
        shutil.rmtree(dest_dir, ignore_errors=True)
        return _redirect(f"/meetings/new?error=总大小超过上限 {settings.upload_max_size_mb}MB")
    except Exception as e:  # noqa: BLE001
        log.error("upload_save_failed", error=str(e), meeting_title=title)
        db.rollback()
        shutil.rmtree(dest_dir, ignore_errors=True)
        return _redirect("/meetings/new?error=保存文件失败，请重试")

    db.commit()

    # 入队转录
    try:
        rq_id = queue_svc.enqueue_transcription(meeting.id)
        meeting.status = "queued"
        db.add(Job(rq_id=rq_id, kind="transcription", meeting_id=meeting.id, status="queued"))
        db.commit()
        log.info("meeting_enqueued", meeting_id=meeting.id, rq_id=rq_id)
        return _redirect(f"/meetings/{meeting.id}?msg=已上传，排队转录中")
    except Exception as e:  # noqa: BLE001
        log.error("enqueue_failed", error=str(e), meeting_id=meeting.id)
        meeting.status = "uploaded"
        db.commit()
        return _redirect(f"/meetings/{meeting.id}?error=文件已保存，但任务入队失败（Redis 不可达？）")


@router.get("/{meeting_id}", response_class=HTMLResponse)
def meeting_detail(
    meeting_id: int,
    request: Request,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
    msg: str | None = None,
    error: str | None = None,
):
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    files = db.execute(
        select(AudioFile).where(AudioFile.meeting_id == meeting_id).order_by(AudioFile.sequence)
    ).scalars().all()
    speakers = {
        s.id: s
        for s in db.execute(
            select(Speaker).where(Speaker.meeting_id == meeting_id)
        ).scalars().all()
    }
    segments = db.execute(
        select(Segment).where(Segment.meeting_id == meeting_id).order_by(Segment.sequence)
    ).scalars().all()
    job = _latest_job(db, meeting_id)
    prompt_preview = build_initial_prompt(db, meeting)

    return templates.TemplateResponse(
        request,
        "meetings/detail.html",
        {
            "user": user,
            "meeting": meeting,
            "files": files,
            "speakers": speakers,
            "segments": segments,
            "job": job,
            "prompt_preview": prompt_preview,
            "msg": msg,
            "error": error,
        },
    )


@router.get("/{meeting_id}/status", response_class=HTMLResponse)
def meeting_status(
    meeting_id: int,
    request: Request,
    response: Response,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    """htmx 轮询用：返回状态片段。转录完成时让前端整页刷新以显示结果。"""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    job = _latest_job(db, meeting_id)
    if meeting.status == "transcribed":
        # 刚轮询到完成 → 整页刷新展示转录文本
        response.headers["HX-Refresh"] = "true"
    return templates.TemplateResponse(
        request,
        "meetings/_status.html",
        {"meeting": meeting, "job": job},
        headers=response.headers,
    )
