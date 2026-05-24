"""会议列表 / 上传向导 / 详情 / 状态轮询 / 分块断点续传"""
import shutil
from datetime import datetime
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.auth import require_login
from app.database import get_db
from app.models import AudioFile, Job, Meeting, Scenario, Segment, Speaker, User
from app.services import queue as queue_svc
from app.services import settings_store, storage
from app.services.prompt import build_initial_prompt
from app.templating import templates

router = APIRouter(prefix="/meetings", tags=["meetings"])
log = structlog.get_logger()

CHUNK = 1024 * 1024
TERMINAL = {"transcribed", "failed"}


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _norm_mode(raw: str) -> str:
    mode = (raw or "").strip().lower()
    return mode if mode in ("off", "auto", "count", "channels") else "auto"


def _opt_int(raw: str) -> int | None:
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else None


def _enqueue(db: Session, meeting: Meeting) -> bool:
    """入队转录 + 建 Job，成功返回 True（失败回退 status=uploaded）。"""
    try:
        rq_id = queue_svc.enqueue_transcription(meeting.id)
        meeting.status = "queued"
        db.add(Job(rq_id=rq_id, kind="transcription", meeting_id=meeting.id, status="queued"))
        db.commit()
        log.info("meeting_enqueued", meeting_id=meeting.id, rq_id=rq_id)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("enqueue_failed", error=str(e), meeting_id=meeting.id)
        meeting.status = "uploaded"
        db.commit()
        return False


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
    max_mb, audio_set, video_set = settings_store.effective_upload(db)
    return templates.TemplateResponse(
        request,
        "meetings/new.html",
        {
            "user": user,
            "scenarios": scenarios,
            "error": error,
            "allowed_audio": sorted(audio_set),
            "allowed_video": sorted(video_set),
            "max_size_mb": max_mb,
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
    diarize_mode: str = Form("auto"),
    num_speakers: str = Form(""),
    min_speakers: str = Form(""),
    max_speakers: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    title = title.strip()
    files = [f for f in files if f and f.filename]
    if not title:
        return _redirect("/meetings/new?error=请填写会议标题")
    if not files:
        return _redirect("/meetings/new?error=请至少选择一个音频或视频文件")

    # 上传限制取数据库有效值（设置页可改）
    max_mb, audio_set, video_set = settings_store.effective_upload(db)
    allowed = audio_set | video_set

    # 扩展名校验（保存前）
    for f in files:
        ext = Path(f.filename).suffix.lower().lstrip(".")
        if ext not in allowed:
            return _redirect(f"/meetings/new?error=不支持的文件类型：.{ext}")

    sid = int(scenario_id) if scenario_id.strip().isdigit() else None
    mode = _norm_mode(diarize_mode)

    meeting = Meeting(
        title=title,
        scenario_id=sid,
        company=company.strip() or None,
        tags=tags.strip() or None,
        held_at=_parse_held_at(held_at),
        language=(language.strip() or "zh")[:8],
        status="uploaded",
        custom_prompt=custom_prompt.strip() or None,
        diarize_mode=mode,
        num_speakers=_opt_int(num_speakers) if mode == "count" else None,
        min_speakers=_opt_int(min_speakers) if mode == "count" else None,
        max_speakers=_opt_int(max_speakers) if mode == "count" else None,
        owner_id=user.id,
    )
    db.add(meeting)
    db.flush()  # 拿到 meeting.id 但还没提交

    budget = max_mb * 1024 * 1024
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
                    media_kind="video" if ext in video_set else "audio",
                    size_bytes=size,
                    sequence=seq,
                    source="upload",
                )
            )
    except ValueError:
        db.rollback()
        shutil.rmtree(dest_dir, ignore_errors=True)
        return _redirect(f"/meetings/new?error=总大小超过上限 {max_mb}MB")
    except Exception as e:  # noqa: BLE001
        log.error("upload_save_failed", error=str(e), meeting_title=title)
        db.rollback()
        shutil.rmtree(dest_dir, ignore_errors=True)
        return _redirect("/meetings/new?error=保存文件失败，请重试")

    db.commit()

    if _enqueue(db, meeting):
        return _redirect(f"/meetings/{meeting.id}?msg=已上传，排队转录中")
    return _redirect(f"/meetings/{meeting.id}?error=文件已保存，但任务入队失败（Redis 不可达？）")


# ===========================================================================
# 分块断点续传：draft（建草稿+占位文件）→ chunk（逐块续传）→ finalize（入队）
# 前端 JS 走这条；无 JS 时回退到上面的整文件 POST /meetings。
# ===========================================================================
class _DraftFile(BaseModel):
    name: str
    size: int


class _DraftRequest(BaseModel):
    title: str
    scenario_id: str | None = None
    company: str = ""
    held_at: str = ""
    language: str = "zh"
    tags: str = ""
    custom_prompt: str = ""
    diarize_mode: str = "auto"
    num_speakers: str = ""
    min_speakers: str = ""
    max_speakers: str = ""
    files: list[_DraftFile]


def _owned_meeting(db: Session, meeting_id: int, user: User) -> Meeting:
    m = db.get(Meeting, meeting_id)
    if not m or m.owner_id != user.id:
        raise HTTPException(status_code=404, detail="会议不存在")
    return m


@router.post("/draft")
def create_draft(
    payload: _DraftRequest,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    title = payload.title.strip()
    files = [f for f in payload.files if f.name and f.size > 0]
    if not title:
        raise HTTPException(status_code=400, detail="请填写会议标题")
    if not files:
        raise HTTPException(status_code=400, detail="请至少选择一个文件")

    max_mb, audio_set, video_set = settings_store.effective_upload(db)
    allowed = audio_set | video_set
    total = 0
    for f in files:
        ext = Path(f.name).suffix.lower().lstrip(".")
        if ext not in allowed:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型：.{ext}")
        total += f.size
    if total > max_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"总大小超过上限 {max_mb}MB")

    sid = int(payload.scenario_id) if (payload.scenario_id or "").strip().isdigit() else None
    mode = _norm_mode(payload.diarize_mode)
    meeting = Meeting(
        title=title,
        scenario_id=sid,
        company=payload.company.strip() or None,
        tags=payload.tags.strip() or None,
        held_at=_parse_held_at(payload.held_at),
        language=(payload.language.strip() or "zh")[:8],
        status="uploading",
        custom_prompt=payload.custom_prompt.strip() or None,
        diarize_mode=mode,
        num_speakers=_opt_int(payload.num_speakers) if mode == "count" else None,
        min_speakers=_opt_int(payload.min_speakers) if mode == "count" else None,
        max_speakers=_opt_int(payload.max_speakers) if mode == "count" else None,
        owner_id=user.id,
    )
    db.add(meeting)
    db.flush()

    dest_dir = storage.meeting_recordings_dir(meeting.id)
    out = []
    for seq, f in enumerate(files):
        ext = Path(f.name).suffix.lower().lstrip(".")
        safe = storage.safe_filename(f.name)
        dest = dest_dir / f"{seq:02d}_{safe}"
        af = AudioFile(
            meeting_id=meeting.id,
            file_path=str(dest),
            original_name=f.name,
            media_kind="video" if ext in video_set else "audio",
            size_bytes=f.size,
            sequence=seq,
            source="upload",
            upload_status="uploading",
            uploaded_bytes=0,
        )
        db.add(af)
        db.flush()
        out.append({"id": af.id, "name": f.name, "size": f.size, "uploaded_bytes": 0})
    db.commit()
    return {"meeting_id": meeting.id, "files": out}


@router.get("/{meeting_id}/files/{file_id}")
def file_status(
    meeting_id: int,
    file_id: int,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    _owned_meeting(db, meeting_id, user)
    af = db.get(AudioFile, file_id)
    if not af or af.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="文件不存在")
    return {
        "id": af.id,
        "size": af.size_bytes or 0,
        "uploaded_bytes": af.uploaded_bytes,
        "status": af.upload_status,
    }


@router.put("/{meeting_id}/files/{file_id}/chunk")
async def upload_chunk(
    meeting_id: int,
    file_id: int,
    request: Request,
    offset: int = 0,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    _owned_meeting(db, meeting_id, user)
    af = db.get(AudioFile, file_id)
    if not af or af.meeting_id != meeting_id:
        raise HTTPException(status_code=404, detail="文件不存在")
    if af.upload_status == "ready":
        return {"uploaded_bytes": af.uploaded_bytes, "status": "ready"}
    # 偏移与服务端不一致 → 409 + 实际偏移，客户端据此续传（断点续传核心）
    if offset != af.uploaded_bytes:
        return JSONResponse(
            status_code=409,
            content={"uploaded_bytes": af.uploaded_bytes, "status": af.upload_status},
        )
    data = await request.body()
    if not data:
        return {"uploaded_bytes": af.uploaded_bytes, "status": af.upload_status}
    total = af.size_bytes or 0
    if af.uploaded_bytes + len(data) > total:
        raise HTTPException(status_code=400, detail="数据超出声明大小")

    path = Path(af.file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    open_mode = "r+b" if path.exists() else "wb"
    with path.open(open_mode) as fh:
        fh.seek(af.uploaded_bytes)
        fh.truncate()          # 丢弃可能的半截尾巴，保证与 uploaded_bytes 一致
        fh.write(data)
    af.uploaded_bytes += len(data)
    if af.uploaded_bytes >= total:
        af.upload_status = "ready"
    db.commit()
    return {"uploaded_bytes": af.uploaded_bytes, "status": af.upload_status}


@router.post("/{meeting_id}/finalize")
def finalize_meeting(
    meeting_id: int,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    meeting = _owned_meeting(db, meeting_id, user)
    files = db.execute(
        select(AudioFile).where(AudioFile.meeting_id == meeting_id)
    ).scalars().all()
    if not files:
        raise HTTPException(status_code=400, detail="没有文件")
    pending = [f for f in files if f.upload_status != "ready"]
    if pending:
        raise HTTPException(status_code=409, detail=f"还有 {len(pending)} 个文件未传完")
    if meeting.status in ("queued", "processing", "transcribed"):
        return {"meeting_id": meeting.id, "status": meeting.status, "enqueued": True}
    ok = _enqueue(db, meeting)
    return {"meeting_id": meeting.id, "status": meeting.status, "enqueued": ok}


@router.post("/{meeting_id}/cancel")
def cancel_meeting(
    meeting_id: int,
    user: User = Depends(require_login),
    db: Session = Depends(get_db),
):
    meeting = _owned_meeting(db, meeting_id, user)
    if meeting.status not in ("uploading", "uploaded"):
        raise HTTPException(status_code=409, detail="该会议不可取消")
    dest_dir = storage.meeting_recordings_dir(meeting.id)
    db.query(AudioFile).filter_by(meeting_id=meeting.id).delete()
    db.delete(meeting)
    db.commit()
    shutil.rmtree(dest_dir, ignore_errors=True)
    return {"ok": True}


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
