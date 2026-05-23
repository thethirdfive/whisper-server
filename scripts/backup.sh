#!/bin/sh
# whisper-server 每日 SQLite 备份脚本
# 由 backup-cron 容器调用

set -e

DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="/data/whisper/db/whisper.db"
BACKUP_DIR="/data/whisper/backups/db"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    echo "❌ [backup] 数据库不存在：$DB_PATH"
    exit 1
fi

echo "📦 [backup] 开始备份 $DB_PATH → $BACKUP_DIR/"

# 1. SQLite 一致性 dump（不会破坏 WAL）
TMP_FILE="$BACKUP_DIR/whisper_${DATE}.db"
sqlite3 "$DB_PATH" ".backup '$TMP_FILE'"

# 2. 压缩
gzip -9 "$TMP_FILE"
SIZE=$(du -h "${TMP_FILE}.gz" | cut -f1)
echo "✅ [backup] 完成：${TMP_FILE}.gz ($SIZE)"

# 3. 清理过期备份
echo "🧹 [backup] 清理 $RETENTION_DAYS 天前的备份..."
DELETED=$(find "$BACKUP_DIR" -name "whisper_*.db.gz" -mtime "+${RETENTION_DAYS}" -delete -print | wc -l)
echo "🧹 [backup] 删除 $DELETED 个过期文件"

# 4. Bark 通知（可选）
if [ -n "$BARK_KEY" ]; then
    MSG="whisper%20backup%20OK%20$SIZE"
    curl -fsS "https://api.day.app/${BARK_KEY}/${MSG}" -o /dev/null \
        && echo "📱 [backup] Bark 通知已发"
fi

# 5. 备份总数
TOTAL=$(ls -1 "$BACKUP_DIR"/whisper_*.db.gz 2>/dev/null | wc -l)
echo "📊 [backup] 当前共 $TOTAL 个备份"
