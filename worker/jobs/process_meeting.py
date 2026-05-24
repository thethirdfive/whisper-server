"""会议处理任务：视频抽轨 → 合并 → WhisperX 转录 + 说话人分离 → 入库

在 worker 镜像内执行（含 ffmpeg / whisperx / CUDA）。whisperx 体积大且需要 GPU，
故在函数内部惰性 import，保证本模块在无 whisperx 环境也能被 import（便于测试/入队）。

说话人分离（meeting.diarize_mode）：
  off       不分离，单声道混音，全部归一个说话人（不打标签）
  auto      单声道混音 + pyannote 自动估计人数（需 HF_TOKEN 且已接受 gated 条款）
  count     同 auto，但把 num/min/max_speakers 传给 pyannote 约束人数
  channels  按声道拆分：每个声道单独转录，声道即说话人（无需 gated 模型，离线可用）
            适合"每人一个麦"的访谈/对话；源必须是 ≥2 声道，否则回退 auto

模型 / 精度 / 分离模型 取数据库有效值（设置页可改，覆盖 .env）；HF_TOKEN 仍只读 .env。
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
from app.services import settings_store
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


def _ffprobe_channels(path: str) -> int | None:
    """探测第一条音轨的声道数（用于判断能否按声道拆分）。"""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=channels", "-of", "json", path,
            ],
            check=True, capture_output=True, text=True,
        )
        streams = json.loads(out.stdout).get("streams", [])
        return int(streams[0]["channels"]) if streams else None
    except Exception as e:  # noqa: BLE001
        log.warning("ffprobe_channels_failed", path=path, error=str(e))
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


def _extract_channel(src: str, ch_index: int, dst: Path) -> None:
    """抽取指定声道为 16kHz 单声道 wav（视频自动取音轨）。"""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", src, "-vn",
            "-af", f"pan=mono|c0=c{ch_index}",
            "-ar", "16000", "-c:a", "pcm_s16le", str(dst),
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
def _gpu_cleanup() -> None:
    """显式回收显存（8GB 卡上，阶段间不释放会 OOM）。"""
    import gc  # noqa: PLC0415

    gc.collect()
    try:
        import torch  # noqa: PLC0415

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        pass


def _is_oom(e: Exception) -> bool:
    return "out of memory" in str(e).lower() or "CUDA failed" in str(e)


def _load_align_transcribe(
    audio_path: str,
    language: str | None,
    initial_prompt: str,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    batch_size: int = 8,
):
    """ASR + 词级对齐。返回 (result, audio)；audio 复用给说话人分离。

    显存不足时自动把 batch_size 减半重试（直到 1），并在转录/对齐各阶段后释放显存，
    以适配 8GB 显存的卡。
    """
    import whisperx  # noqa: PLC0415  惰性导入，避免无 GPU 环境 import 失败

    lang = None if language in (None, "", "auto") else language
    asr_options = {"initial_prompt": initial_prompt} if initial_prompt else None
    log.info("whisperx_load_model", model=model_name, device=device,
             compute_type=compute_type, lang=lang, batch_size=batch_size,
             prompt_len=len(initial_prompt or ""))
    model = whisperx.load_model(
        model_name, device, compute_type=compute_type,
        asr_options=asr_options, language=lang,
    )
    audio = whisperx.load_audio(audio_path)

    # 转录：显存不足则降批重试
    bs = max(1, int(batch_size))
    while True:
        try:
            result = model.transcribe(audio, batch_size=bs, language=lang)
            break
        except RuntimeError as e:
            if not _is_oom(e) or bs <= 1:
                raise
            _gpu_cleanup()
            new_bs = max(1, bs // 2)
            log.warning("transcribe_oom_retry", old_batch=bs, new_batch=new_bs, error=str(e)[:120])
            bs = new_bs
    language_code = result.get("language", lang or "zh")

    # 释放 ASR 模型，给对齐/分离腾显存（8GB 卡必需）
    del model
    _gpu_cleanup()

    # 词级对齐（失败不致命，退化为段级时间戳）
    try:
        model_a, metadata = whisperx.load_align_model(language_code=language_code, device=device)
        result = whisperx.align(
            result["segments"], model_a, metadata, audio, device,
            return_char_alignments=False,
        )
        del model_a
    except Exception as e:  # noqa: BLE001
        log.warning("align_failed", error=str(e), language=language_code)
    finally:
        _gpu_cleanup()

    result["language"] = language_code
    return result, audio


def _diarize(
    audio,
    result: dict,
    *,
    model_name: str,
    device: str,
    hf_token: str,
    num_speakers: int | None,
    min_speakers: int | None,
    max_speakers: int | None,
) -> dict:
    """pyannote 说话人分离，把 speaker 标签贴回每个词/段。需 gated 模型已可下载。"""
    import inspect as _inspect  # noqa: PLC0415

    import whisperx  # noqa: PLC0415

    try:
        from whisperx.diarize import DiarizationPipeline  # noqa: PLC0415
    except Exception:  # noqa: BLE001  旧版本路径
        from whisperx import DiarizationPipeline  # type: ignore  # noqa: PLC0415

    _gpu_cleanup()  # 分离前确保显存最大空闲（8GB 卡）

    # token 参数名随版本变化（新版 token / 旧版 use_auth_token）
    params = _inspect.signature(DiarizationPipeline.__init__).parameters
    diar_kwargs = {"model_name": model_name, "device": device}
    diar_kwargs["token" if "token" in params else "use_auth_token"] = hf_token
    pipe = DiarizationPipeline(**diar_kwargs)

    # 人数约束：指定确切人数优先，否则给 min/max 范围
    call_kwargs: dict[str, int] = {}
    if num_speakers:
        call_kwargs["num_speakers"] = int(num_speakers)
    else:
        if min_speakers:
            call_kwargs["min_speakers"] = int(min_speakers)
        if max_speakers:
            call_kwargs["max_speakers"] = int(max_speakers)

    diarize_segments = pipe(audio, **call_kwargs)
    result = whisperx.assign_word_speakers(diarize_segments, result)
    log.info("diarization_done", **call_kwargs)
    del pipe
    _gpu_cleanup()
    return result


def _transcribe_by_channels(
    files: list[AudioFile],
    work_dir: Path,
    channels: int,
    language: str | None,
    initial_prompt: str,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    batch_size: int = 8,
) -> dict:
    """按声道拆分：每个声道单独转录，声道号即说话人标签，再按时间合并。"""
    merged_segments: list[dict] = []
    language_code: str | None = None

    for c in range(channels):
        ch_wavs: list[Path] = []
        for af in files:
            chw = work_dir / f"{af.sequence:02d}_ch{c}.wav"
            _extract_channel(af.file_path, c, chw)
            ch_wavs.append(chw)
        if len(ch_wavs) == 1:
            ch_audio = ch_wavs[0]
        else:
            ch_audio = work_dir / f"merged_ch{c}.wav"
            _concat_wavs(ch_wavs, ch_audio, work_dir)

        res, _ = _load_align_transcribe(
            str(ch_audio), language, initial_prompt,
            model_name=model_name, device=device, compute_type=compute_type,
            batch_size=batch_size,
        )
        language_code = language_code or res.get("language")
        label = f"声道{c + 1}"
        for seg in res.get("segments", []):
            if (seg.get("text") or "").strip():
                seg["speaker"] = label
                merged_segments.append(seg)

    merged_segments.sort(key=lambda s: float(s.get("start") or 0.0))
    return {"segments": merged_segments, "language": language_code or "zh"}


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

        # 1. 探测每个文件：时长 + 声道数（回填媒体信息）
        total_dur = 0.0
        max_channels = 1
        for af in files:
            dur = _ffprobe_duration(af.file_path)
            if dur:
                af.duration_sec = int(dur)
                total_dur += dur
            ch = _ffprobe_channels(af.file_path)
            if ch:
                af.channels = ch
                max_channels = max(max_channels, ch)
        db.commit()

        # 有效配置（DB 覆盖 .env）；HF_TOKEN 仍只读 .env
        eff_model = str(settings_store.effective(db, "whisper_model"))
        eff_compute = str(settings_store.effective(db, "whisper_compute_type"))
        eff_device = str(settings_store.effective(db, "whisper_device"))
        eff_batch = int(settings_store.effective(db, "whisper_batch_size"))
        eff_diar_model = str(settings_store.effective(db, "diarize_model"))
        hf_token = settings.hf_token

        mode = (meeting.diarize_mode or "auto").lower()
        prompt = build_initial_prompt(db, meeting)

        # 2. 转录（按模式分派）
        if mode == "channels" and max_channels >= 2:
            _set_progress(db, job, progress=25,
                          message=f"按 {max_channels} 声道分轨转录")
            result = _transcribe_by_channels(
                files, work_dir, max_channels, meeting.language, prompt,
                model_name=eff_model, device=eff_device, compute_type=eff_compute,
                batch_size=eff_batch,
            )
        else:
            if mode == "channels":
                log.warning("channel_mode_needs_stereo_fallback", channels=max_channels)
            # 单声道混音
            wavs: list[Path] = []
            for af in files:
                wav = work_dir / f"{af.sequence:02d}.wav"
                _to_wav16k(af.file_path, wav)
                if af.media_kind == "video":
                    af.extracted_audio_path = str(wav)
                wavs.append(wav)
            db.commit()
            _set_progress(db, job, progress=15, message="音频合并")

            if len(wavs) == 1:
                merged = wavs[0]
            else:
                merged = work_dir / "merged.wav"
                _concat_wavs(wavs, merged, work_dir)

            _set_progress(db, job, progress=25, message="加载模型并转录")
            result, audio = _load_align_transcribe(
                str(merged), meeting.language, prompt,
                model_name=eff_model, device=eff_device, compute_type=eff_compute,
                batch_size=eff_batch,
            )

            # 说话人分离（auto / count）
            if mode in ("auto", "count"):
                if hf_token:
                    _set_progress(db, job, progress=70, message="说话人分离")
                    try:
                        result = _diarize(
                            audio, result,
                            model_name=eff_diar_model, device=eff_device, hf_token=hf_token,
                            num_speakers=meeting.num_speakers if mode == "count" else None,
                            min_speakers=meeting.min_speakers if mode == "count" else None,
                            max_speakers=meeting.max_speakers if mode == "count" else None,
                        )
                    except Exception as e:  # noqa: BLE001  分离失败不致命，退化为无说话人
                        log.warning("diarization_failed", error=str(e))
                else:
                    log.warning("diarization_skipped_no_hf_token")

        _set_progress(db, job, progress=85, message="写入转录结果")

        # 3. 落库
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

        log.info("process_meeting_done", meeting_id=meeting_id, segments=n, mode=mode)
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
