"""定时整理（organizer）调度心跳。

cron 拉起的 headless Claude Code 不是常驻服务，app 容器也看不到宿主机 crontab。
所以让整理脚本每次运行时把「计划 / 上次运行时间 / 结果」写回 settings 表（key-value），
设置页据此显示调度是否在跑、跑得怎么样。这些 key 不在 settings_store.EDITABLE 里
（非用户在线编辑项），直接读写 Setting 行。
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Setting

# settings 表里的心跳 key
K_SCHEDULE = "organizer_schedule"          # 人类可读的计划，如 "每天 02:00 (Asia/Shanghai)"
K_LAST_RUN_AT = "organizer_last_run_at"    # ISO8601
K_LAST_STATUS = "organizer_last_run_status"  # running | ok | failed
K_LAST_SUMMARY = "organizer_last_run_summary"  # 一句话结果

_KEYS = (K_SCHEDULE, K_LAST_RUN_AT, K_LAST_STATUS, K_LAST_SUMMARY)


def _set(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value, description="定时整理调度心跳"))
    else:
        row.value = value


def record_run(db: Session, status: str, summary: str = "", schedule: str = "") -> None:
    """整理脚本调用：写入本次运行的状态/时间/结果（schedule 非空时一并更新计划）。"""
    _set(db, K_LAST_RUN_AT, datetime.now().astimezone().isoformat(timespec="seconds"))
    _set(db, K_LAST_STATUS, status)
    _set(db, K_LAST_SUMMARY, summary)
    if schedule:
        _set(db, K_SCHEDULE, schedule)
    db.commit()


def status(db: Session) -> dict:
    """设置页展示用：读出心跳。configured=是否已配置定时计划。"""
    rows = {k: (db.get(Setting, k).value if db.get(Setting, k) else None) for k in _KEYS}
    return {
        "configured": bool(rows[K_SCHEDULE]),
        "schedule": rows[K_SCHEDULE],
        "last_run_at": rows[K_LAST_RUN_AT],
        "last_status": rows[K_LAST_STATUS],
        "last_summary": rows[K_LAST_SUMMARY],
    }
