"""会议处理任务 - 视频抽轨 → 合并 → WhisperX 转录 → 入库

⚠️ TODO Phase 1 后续：完整实现
当前只是签名，让 RQ 能 import 不报错。
"""
import structlog

log = structlog.get_logger()


def process_meeting(meeting_id: int) -> dict:
    """处理一场会议的完整流程

    Args:
        meeting_id: 数据库里的 meeting 主键

    Returns:
        {"meeting_id": int, "status": str, "segments": int}
    """
    log.info("process_meeting_start", meeting_id=meeting_id)

    # TODO: 实现下面步骤
    # 1. 从 DB 拿 meeting + audio_files (included=true, order by sequence)
    # 2. 对每个 file：ffprobe 检测是 audio 还是 video
    # 3. 视频 → ffmpeg 抽音轨到 extracted_audio_path
    # 4. 多文件 → ffmpeg concat 到 merged.wav
    # 5. 拿 scenario 关联的 vocabularies，拼 initial_prompt
    # 6. 跑 whisperx 转录 + 说话人分离
    # 7. 解析结果 → 写 segments / speakers
    # 8. 更新 meeting.status = transcribed

    raise NotImplementedError(
        "process_meeting 实现待 Phase 1 Day 6-7 补完，目前是骨架"
    )
