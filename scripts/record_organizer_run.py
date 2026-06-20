#!/usr/bin/env python
"""把定时整理的一次运行结果写回 settings 表（供设置页显示）。

在 app 容器内执行（与 DB 同进程权限）：
  python /app/scripts/record_organizer_run.py --status running
  python /app/scripts/record_organizer_run.py --status ok --summary "整理 2 成功 / 0 失败"
  python /app/scripts/record_organizer_run.py --status failed --summary "claude 退出码 1"
首次可带 --schedule "每天 02:00 (Asia/Shanghai)" 记录计划。
"""
import argparse

from app.database import SessionLocal
from app.services import scheduler_status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", required=True, choices=["pending", "running", "ok", "failed"])
    ap.add_argument("--summary", default="")
    ap.add_argument("--schedule", default="")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        scheduler_status.record_run(db, args.status, args.summary, args.schedule)
    finally:
        db.close()


if __name__ == "__main__":
    main()
