"""数据目录路径助手

容器内固定布局（见 docker-compose 双盘挂载）：
  /data/whisper/recordings  (HDD) 原始上传音视频，按 meeting_id 分目录
  /data/whisper/outputs     (NVMe) Word / 转录产物
  /data/whisper/inbox       (HDD) watch folder
根目录由 settings.data_root 决定，测试可覆盖为临时目录。
"""
import re
from pathlib import Path

from app.config import get_settings


def data_root() -> Path:
    return Path(get_settings().data_root)


def recordings_dir() -> Path:
    return data_root() / "recordings"


def outputs_dir() -> Path:
    return data_root() / "outputs"


def meeting_recordings_dir(meeting_id: int) -> Path:
    d = recordings_dir() / str(meeting_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


_UNSAFE = re.compile(r"[^A-Za-z0-9._一-鿿-]+")


def safe_filename(name: str) -> str:
    """去掉路径、把不安全字符替换为下划线，避免目录穿越。"""
    base = Path(name or "").name
    cleaned = _UNSAFE.sub("_", base).strip("._")
    return cleaned or "file"
