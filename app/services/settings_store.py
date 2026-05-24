"""可写设置：DB 覆盖 .env。

`settings` 表是一层 key→value(文本) 的覆盖层。读取某个配置时，先看表里有没有
对应行，有就用（按类型转换），没有就回退到 .env / config 单例的默认值。

只暴露一组"运营类"可在线编辑项（EDITABLE）；HF_TOKEN / SECRET / 密码 等敏感密钥
不在其中，页面只做打码只读展示（SENSITIVE_KEYS）。

app（设置页、上传校验、prompt）与 worker（转录时取模型/精度/分离模型）共用本模块，
两端连同一个数据库，所以页面改了配置，worker 下一个任务即生效。
"""
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Setting


@dataclass(frozen=True)
class Field:
    key: str                       # 同 config 属性名 / .env 名（小写）
    label: str                     # 中文标签
    group: str                     # 分组（页面分块）
    type: str = "str"              # str | int | bool | choice
    choices: tuple = ()            # type == choice 时的可选值
    help: str = ""                 # 说明
    restart: bool = False          # 是否需要重启容器才生效


# 可在线编辑的运营类配置（按页面分组排列）
EDITABLE: list[Field] = [
    Field("app_default_locale", "默认界面语言", "通用", "choice", ("zh-CN", "en-US")),
    Field("whisper_model", "Whisper 模型", "转录", "str", help="如 large-v3 / medium / small"),
    Field("whisper_compute_type", "计算精度", "转录", "choice",
          ("int8", "int8_float16", "float16", "float32"),
          help="显存紧张用 int8，质量优先用 float16"),
    Field("whisper_device", "推理设备", "转录", "choice", ("cuda", "cpu"), restart=True),
    Field("whisper_max_prompt_terms", "提示词最多注入词条数", "转录", "int"),
    Field("diarize_model", "说话人分离模型", "转录", "str",
          help="pyannote gated 模型，需在 HF 接受条款"),
    Field("upload_max_size_mb", "上传大小上限 (MB)", "上传", "int"),
    Field("upload_allowed_audio", "允许的音频扩展名", "上传", "str", help="逗号分隔"),
    Field("upload_allowed_video", "允许的视频扩展名", "上传", "str", help="逗号分隔"),
    Field("bark_key", "Bark 通知 Key", "通知", "str", help="留空则不推送"),
    Field("watch_folder_enabled", "看守目录自动导入", "看守目录", "bool", restart=True),
    Field("watch_folder_path", "看守目录路径", "看守目录", "str", restart=True),
    Field("watch_folder_scan_interval_sec", "扫描间隔 (秒)", "看守目录", "int", restart=True),
    Field("log_level", "日志级别", "运行", "choice",
          ("DEBUG", "INFO", "WARNING", "ERROR"), restart=True),
    Field("backup_retention_days", "备份保留天数", "运行", "int"),
]

# 只读、打码展示的敏感项（绝不在 UI 写入）
SENSITIVE_KEYS: list[tuple[str, str]] = [
    ("hf_token", "HuggingFace Token"),
    ("app_secret_key", "应用密钥"),
    ("admin_password_bcrypt", "管理员密码哈希"),
    ("database_url", "数据库地址"),
    ("redis_url", "Redis 地址"),
]

_BY_KEY: dict[str, Field] = {f.key: f for f in EDITABLE}


# --------------------------------------------------------------------------- #
# 类型转换
# --------------------------------------------------------------------------- #
def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "on", "yes")


def _cast(f: Field, raw: str) -> Any:
    if f.type == "int":
        return int(raw)
    if f.type == "bool":
        return _truthy(raw)
    if f.type == "choice" and raw not in f.choices:
        raise ValueError(f"{raw} 不是 {f.key} 的合法取值")
    return raw


# --------------------------------------------------------------------------- #
# 读取有效值（DB 覆盖 .env）
# --------------------------------------------------------------------------- #
def effective(db: Session, key: str) -> Any:
    """返回某 key 的有效值：表里有覆盖就用覆盖，否则回退 .env 默认。"""
    f = _BY_KEY[key]
    default = getattr(get_settings(), key)
    row = db.get(Setting, key)
    if row is None:
        return default
    try:
        return _cast(f, row.value)
    except (ValueError, TypeError):
        return default  # 表里存了脏值就退回默认，避免炸掉调用方


def effective_all(db: Session) -> dict[str, Any]:
    """所有可编辑项的有效值 dict（页面表单回填用）。"""
    rows = {
        r.key: r
        for r in db.execute(
            select(Setting).where(Setting.key.in_(_BY_KEY.keys()))
        ).scalars().all()
    }
    cfg = get_settings()
    out: dict[str, Any] = {}
    for f in EDITABLE:
        if f.key in rows:
            try:
                out[f.key] = _cast(f, rows[f.key].value)
                continue
            except (ValueError, TypeError):
                pass
        out[f.key] = getattr(cfg, f.key)
    return out


def overridden_keys(db: Session) -> set[str]:
    """当前哪些项被 DB 覆盖了（页面上标记"已改"）。"""
    return set(
        db.execute(
            select(Setting.key).where(Setting.key.in_(_BY_KEY.keys()))
        ).scalars().all()
    )


def effective_upload(db: Session) -> tuple[int, set[str], set[str]]:
    """上传校验用：有效的 (大小上限MB, 音频扩展名集合, 视频扩展名集合)。"""
    max_mb = int(effective(db, "upload_max_size_mb"))
    audio = {e.strip().lower() for e in str(effective(db, "upload_allowed_audio")).split(",") if e.strip()}
    video = {e.strip().lower() for e in str(effective(db, "upload_allowed_video")).split(",") if e.strip()}
    return max_mb, audio, video


# --------------------------------------------------------------------------- #
# 写入
# --------------------------------------------------------------------------- #
def save(db: Session, form: dict[str, Any], user_id: int) -> list[str]:
    """把表单值写入 settings 表。只接受 EDITABLE 内的 key。

    返回校验失败的 key 列表；非空则整体回滚不落库。
    bool 项以"表单里是否出现且为真"判定（未勾选 = false）。
    其它项不在表单里就跳过（不动其现有值）。
    """
    errors: list[str] = []
    staged: list[tuple[Field, str]] = []

    for f in EDITABLE:
        if f.type == "bool":
            raw = "true" if _truthy(form.get(f.key, "")) else "false"
        else:
            if f.key not in form:
                continue
            raw = str(form.get(f.key, "")).strip()
        try:
            _cast(f, raw)  # 校验
        except (ValueError, TypeError):
            errors.append(f.key)
            continue
        staged.append((f, raw))

    if errors:
        return errors

    for f, raw in staged:
        row = db.get(Setting, f.key)
        if row is None:
            db.add(Setting(key=f.key, value=raw, description=f.label, updated_by=user_id))
        else:
            row.value = raw
            row.updated_by = user_id
            row.description = f.label
    db.commit()
    return []


def reset(db: Session, key: str) -> None:
    """删除某个覆盖项，恢复 .env 默认。"""
    if key not in _BY_KEY:
        return
    row = db.get(Setting, key)
    if row is not None:
        db.delete(row)
        db.commit()


# --------------------------------------------------------------------------- #
# 敏感项（只读打码）
# --------------------------------------------------------------------------- #
def _mask(v: str) -> str:
    if not v:
        return "（未设置）"
    if len(v) <= 8:
        return "••••"
    return v[:4] + "…" + v[-2:]


def sensitive_display() -> list[dict[str, str]]:
    cfg = get_settings()
    out: list[dict[str, str]] = []
    for key, label in SENSITIVE_KEYS:
        raw = str(getattr(cfg, key, "") or "")
        out.append({"key": key, "label": label, "masked": _mask(raw)})
    return out


def grouped() -> dict[str, list[Field]]:
    """按 group 聚合可编辑项，保持声明顺序。"""
    groups: dict[str, list[Field]] = {}
    for f in EDITABLE:
        groups.setdefault(f.group, []).append(f)
    return groups
