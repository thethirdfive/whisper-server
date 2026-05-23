#!/bin/bash
# ============================================================================
# whisper-server 双盘分层存储初始化
# 在 host 上跑（不是容器内），首次部署或更换盘时执行
#
# 用法:
#   bash scripts/setup-storage.sh         # 用 .env 里的路径
#   HOST_DATA_DIR=/foo HOST_BULK_DIR=/bar bash scripts/setup-storage.sh
# ============================================================================

set -e

# ---------- 读 .env ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$PROJECT_DIR/.env"
    set +a
fi

NVME_BASE="${HOST_DATA_DIR:-/data/whisper}"
HDD_BASE="${HOST_BULK_DIR:-/mnt/data/whisper}"

echo "============================================================"
echo "📦 whisper-server 存储初始化"
echo "============================================================"
echo "  NVMe (速度敏感): $NVME_BASE"
echo "  HDD  (大文件):   $HDD_BASE"
echo ""

# ---------- 健康检查 ----------
echo "🔍 检查目标分区..."

check_path_disk() {
    local path="$1"
    local label="$2"
    local parent_dir
    parent_dir="$(dirname "$path")"

    if [ ! -d "$parent_dir" ]; then
        echo "  ⚠️  $label 父目录 $parent_dir 不存在（首次创建？继续）"
        return
    fi

    local fs avail
    fs=$(df "$parent_dir" | awk 'NR==2 {print $1}')
    avail=$(df -h "$parent_dir" | awk 'NR==2 {print $4}')
    echo "  ✓ $label → 设备 $fs, 可用 $avail"
}

check_path_disk "$NVME_BASE" "NVMe"
check_path_disk "$HDD_BASE"  "HDD"
echo ""

# 校验确实是两块不同的盘（防止用户把两个都设到同一处）
nvme_dev=$(df "$(dirname "$NVME_BASE")" 2>/dev/null | awk 'NR==2 {print $1}')
hdd_dev=$(df "$(dirname "$HDD_BASE")" 2>/dev/null | awk 'NR==2 {print $1}')

if [ -n "$nvme_dev" ] && [ -n "$hdd_dev" ] && [ "$nvme_dev" = "$hdd_dev" ]; then
    echo "⚠️  警告：HOST_DATA_DIR 和 HOST_BULK_DIR 在同一块盘 ($nvme_dev)"
    echo "    分层存储失去意义。是否继续？"
    read -rp "    (y/N) " ok
    [ "$ok" = "y" ] || exit 1
fi

# ---------- 创建目录 ----------
echo "📁 创建 NVMe 目录..."
sudo mkdir -p "$NVME_BASE"/{db,models,outputs}

echo "📁 创建 HDD 目录..."
sudo mkdir -p "$HDD_BASE"/{recordings,inbox,backups}

# ---------- 设置权限 ----------
echo "🔧 设置 owner 为当前用户 ($USER)..."
sudo chown -R "$USER:$USER" "$NVME_BASE" "$HDD_BASE"
chmod 700 "$NVME_BASE" "$HDD_BASE"
chmod 700 "$NVME_BASE/db"  # 数据库目录最严格

# ---------- 验证 ----------
echo ""
echo "✅ 完成。当前结构："
echo ""
echo "  📁 NVMe ($NVME_BASE):"
ls -la "$NVME_BASE" | sed 's/^/      /'
echo ""
echo "  📁 HDD ($HDD_BASE):"
ls -la "$HDD_BASE" | sed 's/^/      /'
echo ""

echo "💾 磁盘占用："
df -h "$NVME_BASE" "$HDD_BASE" | head -1
df -h "$NVME_BASE" "$HDD_BASE" | tail -n +2 | sort -u

echo ""
echo "============================================================"
echo "🎉 存储初始化完成。可以 docker compose up -d 了"
echo "============================================================"
