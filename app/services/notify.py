"""通知：Bark 推送到 iPhone（无 key 则优雅跳过）。

httpx 默认 trust_env=True，会自动用环境里的 HTTP(S)_PROXY，所以在配了代理的
worker / MCP 进程里也能发出去。
"""
from urllib.parse import quote

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger()


def bark(title: str, body: str = "", *, key: str | None = None, url: str | None = None) -> bool:
    """发一条 Bark 通知。key 为空（含未配置）时跳过并返回 False。"""
    bark_key = key if key is not None else get_settings().bark_key
    if not bark_key:
        log.info("bark_skipped_no_key")
        return False
    endpoint = f"https://api.day.app/{bark_key}/{quote(title)}/{quote(body)}"
    params = {"url": url} if url else None
    try:
        r = httpx.get(endpoint, params=params, timeout=10)
        ok = r.status_code == 200
        log.info("bark_sent", ok=ok, status=r.status_code)
        return ok
    except Exception as e:  # noqa: BLE001  通知失败不致命
        log.warning("bark_failed", error=str(e))
        return False
