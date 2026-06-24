#!/usr/bin/env bash
# 安装/更新「定时整理」cron：每天 02:00（服务器时区，本机为 Asia/Shanghai）跑一次整理。
#
# 幂等：重复执行只保留一条。系统 cron 开机自启，故服务器重启后自动恢复，无需 tmux。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO/scripts/organize-reports.sh"
chmod +x "$SCRIPT"

MARK="# whisper-server organizer"
LINE="0 2 * * * $SCRIPT $MARK"

# 去掉旧的同标记行，再追加新行
( crontab -l 2>/dev/null | grep -vF "$MARK" || true ; echo "$LINE" ) | crontab -

echo "✅ 已安装 cron：每天 02:00 整理待办报告"
echo "   服务器时区：$(timedatectl 2>/dev/null | awk -F': *' '/Time zone/{print $2}' || date +%Z)"
crontab -l | grep -F "$MARK"

# 把计划写入 DB，让设置页立刻显示「已启用」
if docker compose -f "$REPO/docker-compose.yml" exec -T app \
     python /app/scripts/record_organizer_run.py --status pending \
     --summary "已安装定时整理，等待首次运行" --schedule "每天 02:00 (Asia/Shanghai)" >/dev/null 2>&1; then
  echo "✅ 已写入调度状态（设置页「定时整理」可见）"
else
  echo "⚠ 写调度状态失败（app 容器未运行？首次整理运行时会自动补上）"
fi

echo
echo "👉 立即手动跑一次测试： bash $SCRIPT  （日志在 $REPO/.organizer-logs/）"
