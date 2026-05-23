"""RQ 入队助手（app 侧）

app 镜像不含 whisperx，所以用字符串引用入队任务函数，worker 镜像执行时再 import。
"""
from redis import Redis
from rq import Queue

from app.config import get_settings

TRANSCRIPTION_QUEUE = "transcription"
JOB_FUNC = "worker.jobs.process_meeting.process_meeting"
# 转录可能很久（large-v3 + 长会议），给 6 小时上限
JOB_TIMEOUT = 6 * 60 * 60


def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url)


def enqueue_transcription(meeting_id: int) -> str:
    """把转录任务推入队列，返回 RQ job id。"""
    q = Queue(TRANSCRIPTION_QUEUE, connection=get_redis())
    job = q.enqueue(JOB_FUNC, meeting_id, job_timeout=JOB_TIMEOUT)
    return job.id
