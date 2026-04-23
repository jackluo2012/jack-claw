#!/bin/bash
# JackClaw 一键初始化脚本
# 用于配置并启动 JackClaw 服务

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查当前目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

info "JackClaw 初始化脚本"
info "项目目录: $PROJECT_ROOT"
echo ""

# 1. 检查 Python 虚拟环境
if [ ! -d ".venv" ]; then
    info "创建 Python 虚拟环境..."
    python3 -m venv .venv
else
    info "虚拟环境已存在"
fi

# 2. 激活虚拟环境并安装依赖
if [ -f "requirements.txt" ]; then
    info "安装依赖包..."
    if [ -f ".venv/bin/uv" ]; then
        # 使用 uv (更快)
        .venv/bin/uv pip install -r requirements.txt
    elif [ -f ".venv/bin/pip" ]; then
        # 使用标准 pip
        .venv/bin/pip install --upgrade pip
        .venv/bin/pip install -r requirements.txt
    else
        error "未找到 pip 或 uv 命令，无法安装依赖"
        exit 1
    fi
else
    warn "未找到 requirements.txt，跳过依赖安装"
fi

# 3. 检查配置文件
if [ ! -f "config.yaml" ]; then
    if [ -f "config.yaml.template" ]; then
        info "创建配置文件 config.yaml..."
        cp config.yaml.template config.yaml
        warn "请编辑 config.yaml 填写必要的配置信息："
        warn "  - feishu.app_id 和 feishu.app_secret (必填)"
        warn "  - memory.db_dsn (如果使用 pgvector)"
        warn "  - 其他可选配置"
        echo ""
        read -p "是否现在编辑配置文件? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${EDITOR:-vi} config.yaml
        fi
    else
        error "未找到 config.yaml.template，无法创建配置文件"
        exit 1
    fi
else
    info "配置文件 config.yaml 已存在"
fi

# 4. 创建必要目录
info "创建数据目录..."
mkdir -p data/workspace
mkdir -p data/ctx
mkdir -p data/logs
mkdir -p data/cron

# 5. 初始化工作区文件
WORKSPACE_DIR="$PROJECT_ROOT/data/workspace"
if [ ! -f "$WORKSPACE_DIR/soul.md" ]; then
    info "初始化工作区文件..."
    if [ -d "workspace-init" ]; then
        cp -r workspace-init/* "$WORKSPACE_DIR/"
        info "已复制工作区初始化文件"
    else
        warn "未找到 workspace-init 目录，跳过工作区文件初始化"
    fi
fi

# 6. 检查 Docker 服务
info "检查 Docker 服务..."
if command -v docker &> /dev/null; then
    info "Docker 已安装"

    # 询问是否启动 pgvector
    if [ -f "pgvector-docker-compose.yaml" ]; then
        read -p "是否启动 pgvector 数据库服务? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            info "启动 pgvector 服务..."
            docker compose -f pgvector-docker-compose.yaml up -d
            info "pgvector 服务已启动"
            echo ""
            warn "请确保 config.yaml 中的 memory.db_dsn 配置正确"
            warn "默认: postgresql://jackclaw:jackclaw123@localhost:5432/jackclaw_memory"
        fi
    fi

    # 询问是否启动 sandbox
    if [ -f "sandbox-docker-compose.yaml" ]; then
        read -p "是否启动 sandbox 服务? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            info "启动 sandbox 服务..."
            docker compose -f sandbox-docker-compose.yaml up -d
            info "sandbox 服务已启动"
            echo ""
            warn "请确保 config.yaml 中的 sandbox.url 配置正确"
            warn "默认: http://localhost:8022/mcp"
        fi
    fi
else
    warn "Docker 未安装，跳过 Docker 服务启动"
fi

# 7. 显示启动命令
echo ""
info "========================================"
info "初始化完成！"
info "========================================"
echo ""
info "启动 JackClaw 服务:"
echo "  source .venv/bin/activate"
echo "  python3 -m jackclaw.main"
echo ""
info "或者使用一键启动脚本:"
echo "  ./start.sh"
echo ""
info "查看日志:"
echo "  tail -f data/logs/jackclaw.log"
echo ""

# 8. 询问是否立即启动
read -p "是否立即启动 JackClaw 服务? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    info "启动 JackClaw 服务..."
    .venv/bin/python3 -m jackclaw.main
fi
