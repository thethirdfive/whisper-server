"""RQ worker 入口 - 监听 Redis 队列，执行任务

目前是骨架，实际转录逻辑见 worker/jobs/process_meeting.py（待实现）。
"""
import logging
import sys

import structlog
from redis import Redis
from rq import Connection, Queue, Worker

from app.config import get_settings

settings = get_settings()


def setup_logging() -> None:
    logging.basicConfig(level=settings.log_level)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level, logging.INFO)
        ),
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer() if settings.log_format == "json"
            else structlog.dev.ConsoleRenderer(),
        ],
    )


def main() -> None:
    setup_logging()
    log = structlog.get_logger()

    log.info(
        "worker_starting",
        redis_url=settings.redis_url,
        whisper_model=settings.whisper_model,
        device=settings.whisper_device,
    )

    redis_conn = Redis.from_url(settings.redis_url)

    # 检查 Redis 连通
    try:
        redis_conn.ping()
        log.info("redis_connected")
    except Exception as e:
        log.error("redis_unreachable", error=str(e))
        sys.exit(1)

    # 监听这些队列（FIFO 优先级）
    queues = ["transcription", "drive_sync", "default"]

    with Connection(redis_conn):
        worker = Worker([Queue(q) for q in queues])
        log.info("worker_ready", queues=queues)
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
