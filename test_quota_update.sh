#!/bin/bash
# 测试自动更新 Token 配置功能

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

info "测试 1: 更新 config.yaml"
echo "----------------------------------------"

# 备份原配置
if [ -f "config.yaml" ]; then
    cp config.yaml config.yaml.backup
    info "已备份 config.yaml"
fi

# 使用示例配额文件测试
if [ -f "quota_example.json" ]; then
    python set_max_token.py quota_example.json --update-config
    info "✓ 测试通过"
else
    warn "quota_example.json 不存在，跳过此测试"
fi

echo ""
info "测试 2: 生成环境变量"
echo "----------------------------------------"

if [ -f "quota_example.json" ]; then
    eval $(python set_max_token.py quota_example.json)
    info "MAX_MODEL_TOKEN=$MAX_MODEL_TOKEN"
    info "MAX_MODEL_NAME=$MAX_MODEL_NAME"
    info "✓ 测试通过"
else
    warn "quota_example.json 不存在，跳过此测试"
fi

echo ""
info "测试 3: 写入 .env 文件"
echo "----------------------------------------"

if [ -f "quota_example.json" ]; then
    python set_max_token.py quota_example.json --env .env.test
    info "✓ 已生成 .env.test"
    cat .env.test
fi

echo ""
info "清理测试文件..."
rm -f .env.test

# 恢复原配置
if [ -f "config.yaml.backup" ]; then
    mv config.yaml.backup config.yaml
    info "已恢复原配置文件"
fi

echo ""
info "✓ 所有测试完成"
