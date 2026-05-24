"""Pydantic Settings - 集中管理所有环境变量"""
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # === 应用 ===
    app_env: Literal["development", "production"] = "production"
    app_secret_key: str = "change-me-please"
    app_public_url: str = "http://localhost:18080"
    app_default_locale: Literal["zh-CN", "en-US"] = "zh-CN"
    app_timezone: str = "Asia/Shanghai"

    # === 鉴权 ===
    admin_username: str = "ethan"
    admin_email: str | None = None
    admin_display_name: str = "Ethan"
    admin_password_bcrypt: str = ""
    session_lifetime_days: int = 30

    # === 数据库 ===
    database_url: str = "sqlite:////data/whisper/db/whisper.db"

    # === Redis ===
    redis_url: str = "redis://redis:6379/0"

    # === WhisperX ===
    hf_token: str = ""
    whisper_model: str = "large-v3"
    diarize_model: str = "pyannote/speaker-diarization-community-1"
    whisper_device: Literal["cuda", "cpu"] = "cuda"
    whisper_compute_type: str = "int8"
    whisper_batch_size: int = 8  # 转录批大小；显存不足会自动降批重试。8GB 显存建议 4–8
    whisper_max_prompt_terms: int = 80

    # === Google Drive ===
    gdrive_credentials_json: str = "/data/whisper/gdrive_creds.json"
    gdrive_root_folder_id: str = ""
    gdrive_meeting_folder_id: str = ""
    gdrive_interview_folder_id: str = ""
    gdrive_training_folder_id: str = ""

    # === 通知 ===
    bark_key: str = ""

    # === 上传限制 ===
    upload_max_size_mb: int = 4096
    upload_allowed_audio: str = "m4a,mp3,wav,flac,aac,ogg,opus,aif,aiff,wma"
    upload_allowed_video: str = "mp4,mov,mkv,avi,flv,webm,m4v,mpeg,3gp"

    # === Watch folder ===
    watch_folder_enabled: bool = False
    watch_folder_path: str = "/data/whisper/inbox"
    watch_folder_scan_interval_sec: int = 60

    # === 备份 ===
    backup_retention_days: int = 30
    backup_cron_schedule: str = "0 3 * * *"

    # === 日志 ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    # === 数据目录 ===
    host_data_dir: str = "/data/whisper"      # host NVMe（bind mount 源）
    host_bulk_dir: str = "/mnt/data/whisper"  # host HDD（bind mount 源）
    # 容器内数据根（bind mount 后固定为 /data/whisper；测试时可指向临时目录）
    data_root: str = "/data/whisper"

    @property
    def allowed_audio_set(self) -> set[str]:
        return {e.strip().lower() for e in self.upload_allowed_audio.split(",") if e.strip()}

    @property
    def allowed_video_set(self) -> set[str]:
        return {e.strip().lower() for e in self.upload_allowed_video.split(",") if e.strip()}

    @property
    def allowed_extensions(self) -> set[str]:
        return self.allowed_audio_set | self.allowed_video_set


# 单例
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
