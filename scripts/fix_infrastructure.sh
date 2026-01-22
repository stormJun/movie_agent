#!/bin/bash
# 迁移为 backend/ 统一后端目录（server 仅保留 API 层）

set -e

PROJECT_ROOT="/Users/songxijun/workspace/otherProject/graph-rag-agent"
cd "$PROJECT_ROOT"

if [ -d "backend" ]; then
    echo "backend/ 已存在，此脚本面向旧结构；无需再次执行。"
    exit 0
fi

echo "=========================================="
echo "迁移为 backend/ 统一后端目录（server 仅保留 API 层）"
echo "=========================================="

# 分析当前状态
echo ""
echo "📊 当前状态："
echo "  ✅ /backend/ → 统一后端目录"
echo "  ✅ /backend/graphrag_agent/ → 核心引擎"
echo "  ✅ /backend/application/ → 应用服务层（业务编排）"
echo "  ✅ /backend/domain/ → 领域层（语义/实体）"
echo "  ✅ /backend/infrastructure/ → 技术基础设施"
echo "  ✅ /backend/config/ → 服务配置"
echo "  ✅ /backend/server/ → API 入口"
echo ""

# 执行迁移（幂等）
mkdir -p backend

move_dir() {
    local src="$1"
    local dest="$2"
    if [ -d "$src" ]; then
        if [ -e "$dest" ]; then
            echo "⚠️  $dest 已存在，跳过 $src"
        else
            echo "🔄 迁移: $src → $dest"
            mv "$src" "$dest"
            echo "✅ 已完成"
        fi
    fi
}

merge_dir() {
    local src="$1"
    local dest="$2"
    if [ -d "$src" ]; then
        echo "🔄 合并: $src → $dest"
        mkdir -p "$dest"
        for item in "$src"/*; do
            name="$(basename "$item")"
            if [ -e "$dest/$name" ]; then
                echo "⚠️  $dest/$name 已存在，跳过 $item"
            else
                mv "$item" "$dest/"
            fi
        done
        rmdir "$src" 2>/dev/null || true
    fi
}

move_dir "graphrag_agent" "backend/graphrag_agent"
move_dir "application" "backend/application"
move_dir "domain" "backend/domain"
move_dir "infrastructure" "backend/infrastructure"
move_dir "config" "backend/config"

merge_dir "server/application" "backend/application"
merge_dir "server/domain" "backend/domain"
merge_dir "server/infrastructure" "backend/infrastructure"
merge_dir "server/server_config" "backend/config"

if [ -d "server" ]; then
    merge_dir "server" "backend/server"
    rmdir server 2>/dev/null || true
fi

# 更新导入路径
echo ""
echo "🔧 更新导入路径..."
find . -type f -name "*.py" \
    ! -path "./.venv/*" \
    ! -path "./files/*" \
    ! -path "./.git/*" \
    ! -path "./__pycache__/*" \
    -exec sed -i '' \
    -e 's/from graphrag_agent\./from graphrag_agent./g' \
    -e 's/from graphrag_agent import/from graphrag_agent import/g' \
    -e 's/from application\./from application./g' \
    -e 's/from application import/from application import/g' \
    -e 's/from domain\./from domain./g' \
    -e 's/from domain import/from domain import/g' \
    -e 's/from infrastructure\./from infrastructure./g' \
    -e 's/from infrastructure import/from infrastructure import/g' \
    -e 's/from config\./from config./g' \
    -e 's/from config import/from config import/g' \
    -e 's/from server\.application\./from application./g' \
    -e 's/from server\.application import/from application import/g' \
    -e 's/from server\.domain\./from domain./g' \
    -e 's/from server\.domain import/from domain import/g' \
    -e 's/from server\.infrastructure\./from infrastructure./g' \
    -e 's/from server\.infrastructure import/from infrastructure import/g' \
    -e 's/from server\.services\.orchestrator/from infrastructure.routing.orchestrator/g' \
    -e 's/from server\.services\.kb_router/from infrastructure.routing.kb_router/g' \
    -e 's/from server\.services\.rag_factory/from infrastructure.agents.rag_factory/g' \
    -e 's/from server\.services\.business_agents/from application.services.business_agents/g' \
    -e 's/from server\.services\.chat_service/from application.services.chat_service/g' \
    -e 's/from server\.services\.agent_service/from application.services.agent_service/g' \
    -e 's/from server\.services\.kg_service/from application.services.kg_service/g' \
    -e 's/from server\.utils\./from infrastructure.utils./g' \
    -e 's/from server\.utils import/from infrastructure.utils import/g' \
    -e 's/from server\.server_config\./from config./g' \
    -e 's/from server\.config\./from config./g' \
    {} \;

echo "✅ 已更新所有Python导入"

# 创建说明文档
mkdir -p backend/application
cat > backend/application/README.md << 'EOF'
# Application Layer

This directory contains application services and business logic orchestration.

## Structure

```
backend/application/
├── chat/               # Chat handlers
├── knowledge_graph/    # KG use cases
├── services/           # Legacy services (compat)
└── ports/              # Application ports
```

## Responsibility

This is the **Application Layer** in DDD architecture. It orchestrates business logic
and coordinates between the domain layer, core engine, and infrastructure.

## Difference from `backend/infrastructure/`

- **`/backend/infrastructure/`**: Technical building blocks (database, cache, models)
- **`/backend/application/`**: Business services and orchestration logic
- **`graphrag_agent`**: Accesses infrastructure via `graphrag_agent.ports.*` providers
EOF

echo "✅ 已创建 backend/application/README.md"

echo ""
echo "=========================================="
echo "✅ 修复完成！"
echo "=========================================="
echo ""
echo "变更总结："
echo "  📁 graphrag_agent → backend/graphrag_agent"
echo "  📁 application → backend/application"
echo "  📁 domain → backend/domain"
echo "  📁 infrastructure → backend/infrastructure"
echo "  📁 config → backend/config"
echo "  📁 server → backend/server"
echo "  📝 更新所有相关导入"
echo ""
echo "现在的结构："
echo "  ✅ /backend/graphrag_agent/ → 核心引擎"
echo "  ✅ /backend/application/    → 应用服务层"
echo "  ✅ /backend/domain/         → 领域层"
echo "  ✅ /backend/infrastructure/ → 技术基础设施"
echo "  ✅ /backend/config/         → 服务配置"
echo "  ✅ /backend/server/         → API 入口"
echo ""
echo "导入示例："
echo "  from infrastructure.bootstrap import bootstrap_core_ports"
echo "  bootstrap_core_ports()"
echo "  from graphrag_agent.ports.neo4jdb import get_db_manager"
echo "  from application.chat.handlers.chat_handler import ChatHandler"
echo ""
