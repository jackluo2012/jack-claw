#!/bin/bash
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

# 自动更新最大 Token 配额
QUOTA_FILE="${QUOTA_FILE:-$PROJECT_ROOT/quota.json}"
if [ -f "$QUOTA_FILE" ]; then
    info "检测到配额文件，正在更新最大 Token 配置..."
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

# 启动服务（使用 venv 中的 python）
.venv/bin/python3 -m jackclaw.main
