#!/bin/sh
# whisper-server app 启动脚本
# 顺序：检查双盘挂载点 → 跑 Alembic 迁移 → 创建管理员 → 启动 uvicorn

set -e

# 1. 检查 6 个挂载点是否就绪（必须先在 host 上 setup-storage.sh）
REQUIRED_DIRS="/data/whisper/db /data/whisper/models /data/whisper/outputs \
               /data/whisper/recordings /data/whisper/inbox /data/whisper/backups"

for d in $REQUIRED_DIRS; do
    if [ ! -d "$d" ]; then
        echo "❌ 目录不存在：$d"
        echo "   请先在 host 上运行: bash scripts/setup-storage.sh"
        exit 1
    fi
done

# 验证 db 目录可写（SQLite 需要）
touch /data/whisper/db/.write-test 2>/dev/null || {
    echo "❌ /data/whisper/db 不可写"
    echo "   请检查 host 上的 ${HOST_DATA_DIR}/db 权限"
    exit 1
}
rm -f /data/whisper/db/.write-test

echo "✅ [entrypoint] 6 个数据目录就绪"

echo "📦 [entrypoint] 跑 Alembic 迁移..."
alembic upgrade head

echo "👤 [entrypoint] 检查/创建管理员账号..."
python /app/scripts/create_admin.py

echo "🚀 [entrypoint] 启动应用：$@"
exec "$@"
