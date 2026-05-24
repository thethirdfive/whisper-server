"""Google Drive 服务端拉取。

浏览器用 Google Picker 选文件、拿到短期 access token + fileId，发给服务端；
服务端用该 token 直接从 Drive 下载文件字节（机房↔Google，绕开用户 WAN 上行）。

注意：homeserver 在国内，访问 googleapis.com 需走代理 —— httpx 默认 trust_env，
会用容器里的 HTTP(S)_PROXY（compose 已给 app 配上）。
"""
from pathlib import Path

import httpx
import structlog

log = structlog.get_logger()

_DL_URL = "https://www.googleapis.com/drive/v3/files/{fid}"
_META_URL = "https://www.googleapis.com/drive/v3/files/{fid}"
_CHUNK = 4 * 1024 * 1024


def file_meta(file_id: str, access_token: str) -> dict:
    """取文件名/大小（校验 token + 文件可访问）。"""
    r = httpx.get(
        _META_URL.format(fid=file_id),
        params={"fields": "id,name,size,mimeType", "supportsAllDrives": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def download_file(file_id: str, access_token: str, dest: Path) -> int:
    """流式下载到 dest，返回字节数。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with httpx.stream(
        "GET",
        _DL_URL.format(fid=file_id),
        params={"alt": "media", "supportsAllDrives": "true"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=httpx.Timeout(30.0, read=None),
    ) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(_CHUNK):
                f.write(chunk)
                size += len(chunk)
    log.info("gdrive_downloaded", file_id=file_id, bytes=size, dest=str(dest))
    return size
