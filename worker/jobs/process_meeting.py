"""会议处理任务：视频抽轨 → 合并 → WhisperX 转录 + 说话人分离 → 入库

在 worker 镜像内执行（含 ffmpeg / whisperx / CUDA）。whisperx 体积大且需要 GPU，
故在函数内部惰性 import，保证本模块在无 whisperx 环境也能被 import（便于测试/入队）。

流程：
  1. 取 meeting + audio_files(included, 按 sequence)
  2. 每个文件 ffprobe 取时长；视频抽音轨；统一转 16k 单声道 wav
  3. 多文件 ffmpeg concat 合并成一条音轨
  4. 由场景词库拼 initial_prompt
  5. whisperx 转录 → 对齐 → 说话人分离
  6. 写 speakers / segments，更新 meeting.status / duration_sec 与 job 进度
"""
import json
import shutil
import subprocess
import traceback
from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import AudioFile, Job, Meeting, Segment, Speaker
from app.services.prompt import build_initial_prompt

log = structlog.get_logger()
settings = get_settings()


# ---------------------------------------------------------------------------
# ffmpeg / ffprobe 助手
# ---------------------------------------------------------------------------
def _ffprobe_duration(path: str) -> float | None:
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "json", path,
            ],
            check=True, capture_output=True, text=True,
        )
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception as e:  # noqa: BLE001
        log.warning("ffprobe_failed", path=path, error=str(e))
        return None


def _to_wav16k(src: str, dst: Path) -> None:
    """转 16kHz 单声道 wav（whisper 标准输入）。视频会自动只取音轨。"""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", src,
            "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "pcm_s16le", str(dst),
        ],
        check=True, capture_output=True,
    )


def _concat_wavs(wavs: list[Path], dst: Path, work_dir: Path) -> None:
    """用 concat demuxer 把同格式 wav 拼成一条（-c copy 不重新编码）。"""
    list_file = work_dir / "concat.txt"
    list_file.write_text("".join(f"file '{w}'\n" for w in wavs), encoding="utf-8")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(dst)],
        check=True, capture_output=True,
    )


# ---------------------------------------------------------------------------
# job 进度
# ---------------------------------------------------------------------------
def _set_progress(db, job, *, progress=None, message=None, status=None, error=None):
    if job is None:
        return
    if progress is not None:
        job.progress = progress
    if message is not None:
        job.message = message
    if status is not None:
        job.status = status
    if error is not None:
        job.error = error
    db.commit()


# ---------------------------------------------------------------------------
# 转录核心（惰性 import whisperx）
# ---------------------------------------------------------------------------
def _transcribe(audio_path: str, language: str | None, initial_prompt: str) -> dict:
    import whisperx  # noqa: PLC0415  惰性导入，避免无 GPU 环境 import 失败

    device = settings.whisper_device
    compute_type = settings.whisper_compute_type
    lang = None if language in (None, "", "auto") else language

    asr_options = {"initial_prompt": initial_prompt} if initial_prompt else None
    log.info("whisperx_load_model", model=settings.whisper_model, device=device,
             compute_type=compute_type, lang=lang, prompt_len=len(initial_prompt or ""))
    model = whisperx.load_model(
        settings.whisper_model, device, compute_type=compute_type,
        asr_options=asr_options, language=lang,
    )
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=16, language=lang)
    language_code = result.get("language", lang or "zh")

    # 词级对齐（失败不致命，退化为段级时间戳）
    try:
        model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
        result = whisperx.align(
            result["segments"], model_a, metadata, audio, device,
            return_char_alignments=False,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("align_failed", error=str(e), language=language_code)

    # 说话人分离（需要 HF token；失败不致命，退化为无说话人）
    if settings.hf_token:
        try:
            import inspect as _inspect

            try:
                from whisperx.diarize import DiarizationPipeline
            except Exception:  # noqa: BLE001  旧版本路径
                from whisperx import DiarizationPipeline  # type: ignore
            # token 参数名随版本变化（新版 token / 旧版 use_auth_token）
            diar_kwargs = {"model_name": settings.diarize_model, "device": device}
            params = _inspect.signature(DiarizationPipeline.__init__).parameters
            diar_kwargs["token" if "token" in params else "use_auth_token"] = settings.hf_token
            diarize_model = DiarizationPipeline(**diar_kwargs)
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            log.info("diarization_done")
        except Exception as e:  # noqa: BLE001
            log.warning("diarization_failed", error=str(e))
    else:
        log.warning("diarization_skipped_no_hf_token")

    result["language"] = language_code
    return result


def _write_results(db, meeting: Meeting, result: dict) -> int:
    """把 whisperx 结果写入 speakers / segments，返回 segment 数。"""
    speaker_rows: dict[str, Speaker] = {}

    def speaker_for(label: str | None) -> int | None:
        if not label:
            return None
        if label not in speaker_rows:
            sp = Speaker(meeting_id=meeting.id, label=label)
            db.add(sp)
            db.flush()
            speaker_rows[label] = sp
        return speaker_rows[label].id

    count = 0
    for seg in result.get("segments", []):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        db.add(
            Segment(
                meeting_id=meeting.id,
                speaker_id=speaker_for(seg.get("speaker")),
                start_sec=float(seg.get("start") or 0.0),
                end_sec=float(seg.get("end") or 0.0),
                text=text,
                sequence=count,
            )
        )
        count += 1
    db.flush()
    return count


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def process_meeting(meeting_id: int) -> dict:
    log.info("process_meeting_start", meeting_id=meeting_id)
    db = SessionLocal()
    job = db.execute(
        select(Job).where(Job.meeting_id == meeting_id).order_by(Job.id.desc()).limit(1)
    ).scalar_one_or_none()

    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        db.close()
        raise ValueError(f"meeting {meeting_id} 不存在")

    try:
        meeting.status = "processing"
        _set_progress(db, job, progress=5, message="准备音频", status="processing")
        if job is not None:
            job.started_at = datetime.utcnow()
            db.commit()

        # 幂等：清掉上次处理残留（先 segments 再 speakers，避免 FK 冲突）
        db.query(Segment).filter_by(meeting_id=meeting_id).delete()
        db.query(Speaker).filter_by(meeting_id=meeting_id).delete()
        db.commit()

        files = db.execute(
            select(AudioFile)
            .where(AudioFile.meeting_id == meeting_id, AudioFile.included.is_(True))
            .order_by(AudioFile.sequence)
        ).scalars().all()
        if not files:
            raise ValueError("没有可用的音频文件")

        work_dir = Path(files[0].file_path).parent / "_work"
        if work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. 抽轨 + 统一转 wav，顺带回填时长/媒体信息
        wavs: list[Path] = []
        total_dur = 0.0
        for af in files:
            dur = _ffprobe_duration(af.file_path)
            if dur:
                af.duration_sec = int(dur)
                total_dur += dur
            wav = work_dir / f"{af.sequence:02d}.wav"
            _to_wav16k(af.file_path, wav)
            if af.media_kind == "video":
                af.extracted_audio_path = str(wav)
            wavs.append(wav)
        db.commit()
        _set_progress(db, job, progress=15, message="音频合并")

        # 2. 合并
        if len(wavs) == 1:
            merged = wavs[0]
        else:
            merged = work_dir / "merged.wav"
            _concat_wavs(wavs, merged, work_dir)

        # 3. prompt
        prompt = build_initial_prompt(db, meeting)
        _set_progress(db, job, progress=25, message="加载模型并转录")

        # 4. 转录
        result = _transcribe(str(merged), meeting.language, prompt)
        _set_progress(db, job, progress=85, message="写入转录结果")

        # 5. 落库
        n = _write_results(db, meeting, result)

        meeting.status = "transcribed"
        if total_dur:
            meeting.duration_sec = int(total_dur)
        if result.get("language"):
            meeting.language = result["language"][:8]
        db.commit()
        if job is not None:
            job.finished_at = datetime.utcnow()
        _set_progress(db, job, progress=100, message=f"完成，{n} 段", status="finished")

        # 清理中间文件
        shutil.rmtree(work_dir, ignore_errors=True)

        log.info("process_meeting_done", meeting_id=meeting_id, segments=n)
        return {"meeting_id": meeting_id, "status": "transcribed", "segments": n}

    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        log.error("process_meeting_failed", meeting_id=meeting_id, error=str(e))
        db.rollback()
        meeting = db.get(Meeting, meeting_id)
        if meeting:
            meeting.status = "failed"
        if job is not None:
            job = db.get(Job, job.id)
            if job:
                job.status = "failed"
                job.error = tb[-4000:]
                job.finished_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        db.close()
