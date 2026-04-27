#!/usr/bin/env bash
# JackClaw 一键启动脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

PID_FILE="$PROJECT_ROOT/.jackclaw.pid"

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        warn "JackClaw 已在运行 (PID $OLD_PID)，如需重启请先运行 ./stop.sh"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# 检查虚拟环境
if [ ! -d ".venv" ]; then
    warn "虚拟环境不存在，请先运行 ./init.sh 进行初始化"
    exit 1
fi

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    warn "配置文件不存在，请先运行 ./init.sh 进行初始化"
    exit 1
fi

# 清理 __pycache__，避免缓存导致旧代码生效
find "$PROJECT_ROOT/jackclaw" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true

# 自动更新最大 Token 配额
QUOTA_FILE="${QUOTA_FILE:-$PROJECT_ROOT/quota.json}"
if [ -f "$QUOTA_FILE" ]; then
    info "检测到配额文件，正在更新最大 Token 配额..."
    if "$PROJECT_ROOT/set_max_token.py" "$QUOTA_FILE" --update-config; then
        info "✓ Token 配置已自动更新"
    else
        warn "⚠ Token 配置更新失败，使用现有配置"
    fi
    echo ""
else
    info "未找到配额文件 ($QUOTA_FILE)"
    info "提示: 可设置 QUOTA_FILE 环境变量指定配额文件路径，或将配额文件保存为 $PROJECT_ROOT/quota.json"
    echo ""
fi

# 显示启动信息
info "启动 JackClaw 服务..."
info "项目目录: $PROJECT_ROOT"
echo ""

# 启动服务（后台运行，记录 PID）
nohup .venv/bin/python3 -m jackclaw.main >> "$PROJECT_ROOT/data/logs/jackclaw.log" 2>&1 &
echo $! > "$PID_FILE"
info "JackClaw 已后台启动 (PID $(cat "$PID_FILE"))"
info "日志文件: $PROJECT_ROOT/data/logs/jackclaw.log"
info "停止服务: ./stop.sh"
