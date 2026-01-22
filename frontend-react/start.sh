#!/bin/bash

# GraphRAG React 前端启动脚本

echo "🚀 启动 GraphRAG React 前端..."

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "📦 首次运行，安装依赖..."
    npm install
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚙️  创建 .env 配置文件..."
    cp .env.example .env
    echo "✅ 已创建 .env，请检查配置是否正确"
fi

# 启动开发服务器
echo "🌐 启动开发服务器 (http://localhost:5174)..."
npm run dev
