#!/bin/sh
# whisper-server app 启动脚本
# 顺序：等 DB 目录就绪 → 跑 Alembic 迁移 → 创建管理员 → 启动 uvicorn

set -e

# 1. 确保数据目录存在
mkdir -p /data/whisper/db /data/whisper/recordings /data/whisper/outputs \
         /data/whisper/models /data/whisper/inbox /data/whisper/backups

echo "📦 [entrypoint] 跑 Alembic 迁移..."
alembic upgrade head

echo "👤 [entrypoint] 检查/创建管理员账号..."
python /app/scripts/create_admin.py

echo "🚀 [entrypoint] 启动应用：$@"
exec "$@"
