#!/usr/bin/env bash
# 定时整理：cron 拉起 headless Claude Code，经 whisper MCP 把「待整理」会议生成 HTML 报告。
#
# 无状态一次性运行：跑完即退出，不需要常驻 tmux；cron 由系统在开机时自启 → 服务器重启
# 后无需任何手工操作即可恢复。走 Claude Max 订阅、零额外 API 费用。
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

# cron 的 PATH 很精简，补上 claude / docker / node 常见安装路径
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/snap/bin:$PATH"

LOG_DIR="$REPO/.organizer-logs"
mkdir -p "$LOG_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
LOG="$LOG_DIR/run_$TS.log"

SCHEDULE_LABEL="每天 02:00 (Asia/Shanghai)"
PROMPT="$(cat "$REPO/docs/organize-prompt.md")"
ALLOWED="mcp__whisper__list_pending_reports mcp__whisper__get_meeting mcp__whisper__claim_report mcp__whisper__submit_report mcp__whisper__report_failed"

heartbeat() {  # $1=status $2=summary —— 把运行状态写回 DB（设置页可见）
  docker compose exec -T app python /app/scripts/record_organizer_run.py \
    --status "$1" --summary "$2" --schedule "$SCHEDULE_LABEL" >/dev/null 2>&1 || true
}

{
  echo "=== organize-reports $TS ==="
  heartbeat running "整理进行中…"

  OUT="$(claude -p "$PROMPT" \
    --mcp-config "$REPO/.mcp.json" --strict-mcp-config \
    --allowedTools $ALLOWED \
    --permission-mode acceptEdits \
    --output-format text 2>&1)"
  RC=$?
  echo "$OUT"

  # 取整理器最后一行非空输出当作结果摘要（prompt 第 6 步会汇报「成功 N / 失败 M」）
  LASTLINE="$(printf '%s\n' "$OUT" | grep -v '^[[:space:]]*$' | tail -1 | cut -c1-200)"

  if [ "$RC" -eq 0 ]; then
    heartbeat ok "${LASTLINE:-整理完成}（日志 run_$TS.log）"
    echo "✅ done rc=0"
  else
    heartbeat failed "claude 退出码 $RC：${LASTLINE:-见日志 run_$TS.log}"
    echo "❌ failed rc=$RC"
  fi
} >>"$LOG" 2>&1

# 只保留最近 30 个日志
ls -1t "$LOG_DIR"/run_*.log 2>/dev/null | tail -n +31 | xargs -r rm -f
