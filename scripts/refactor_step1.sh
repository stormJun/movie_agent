#!/bin/bash
# 阶段1：迁移到 backend/ 统一后端目录

set -e  # 遇到错误立即退出

PROJECT_ROOT="/Users/songxijun/workspace/otherProject/graph-rag-agent"
cd "$PROJECT_ROOT"

if [ -d "backend" ]; then
    echo "backend/ 已存在，此脚本面向旧结构；无需执行。"
    exit 0
fi

echo "=========================================="
echo "架构重构 - 阶段1：迁移到 backend/ 统一后端目录"
echo "=========================================="

# 1. 备份关键配置
if [ -f "config/rag.py" ]; then
    echo "📦 备份配置文件..."
    cp config/rag.py config/rag.py.backup
    echo "✅ 已备份: config/rag.py.backup"
fi

# 2. 执行迁移脚本
if [ -f "scripts/fix_infrastructure.sh" ]; then
    echo "🔄 执行迁移脚本: scripts/fix_infrastructure.sh"
    bash scripts/fix_infrastructure.sh
else
    echo "⚠️  scripts/fix_infrastructure.sh 不存在，跳过自动迁移"
fi

# 3. 检查遗留目录
if [ -d "rag_layer" ]; then
    echo "⚠️  发现旧 rag_layer/（已弃用），请手动迁移或删除"
fi

echo ""
echo "=========================================="
echo "✅ 阶段1完成！"
echo "=========================================="
echo ""
echo "下一步："
echo "1. 运行测试确保功能正常"
echo "2. 更新文档中的导入路径"
echo "3. 运行前先注入 provider（infrastructure.bootstrap.bootstrap_core_ports）"
echo ""
if [ -f "backend/config/rag.py.backup" ]; then
    echo "备份文件位置: $PROJECT_ROOT/backend/config/rag.py.backup"
elif [ -f "config/rag.py.backup" ]; then
    echo "备份文件位置: $PROJECT_ROOT/config/rag.py.backup"
fi
