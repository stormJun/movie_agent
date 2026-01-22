#!/bin/bash
# 电影数据快速处理脚本
#
# 使用方法:
#   bash data/movie/quickstart.sh [step]
#
# 参数:
#   step - 可选，指定要执行的步骤
#          1, full    - 完整数据预处理
#          all        - 执行所有步骤（默认）
#
# 示例:
#   bash data/movie/quickstart.sh              # 执行所有步骤
#   bash data/movie/quickstart.sh full         # 仅运行数据预处理

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🎬 电影数据处理快速启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 检查 Python 环境（强制 Python 3.10）
PYTHON_BIN=""
if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3.10 &> /dev/null; then
    PYTHON_BIN="python3.10"
elif command -v python3 &> /dev/null; then
    PYTHON_BIN="python3"
fi

if [ -z "$PYTHON_BIN" ]; then
    echo -e "${RED}❌ 错误: 未找到可用的 Python（需要 Python 3.10）${NC}"
    echo -e "${YELLOW}建议在项目根目录创建 venv：python3.10 -m venv .venv && source .venv/bin/activate${NC}"
    exit 1
fi

PY_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
if [ "$PY_VER" != "3.10" ]; then
    echo -e "${RED}❌ 错误: Python 版本不符合要求（当前: ${PY_VER:-unknown}，需要: 3.10）${NC}"
    echo -e "${YELLOW}请使用 Python 3.10 创建项目 venv（推荐）：python3.10 -m venv .venv && source .venv/bin/activate${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 环境检查通过（$PYTHON_BIN, $PY_VER）${NC}"
echo ""

# 获取要执行的步骤
STEP="${1:-all}"

# 步骤 1: 运行完整数据预处理
if [[ "$STEP" == "1" || "$STEP" == "full" || "$STEP" == "all" ]]; then
    echo -e "${YELLOW}⚙️  步骤 1/1: 运行完整数据预处理...${NC}"
    echo ""

    # 检查源数据目录
    SOURCE_DIR="SparrowRecSys-master/target/classes/webroot/sampledata"
    if [ ! -d "$SOURCE_DIR" ]; then
        echo -e "${RED}❌ 错误: 源数据目录不存在: $SOURCE_DIR${NC}"
        echo -e "${YELLOW}请确保 SparrowRecSys-master 目录在项目根目录下${NC}\n"
        exit 1
    fi

    echo -e "${BLUE}源数据目录: $SOURCE_DIR${NC}"
    echo -e "${BLUE}预计耗时: 12-20 分钟${NC}"
    echo ""
    read -p "是否继续? (y/n) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        "$PYTHON_BIN" data/movie/movie_data_preprocessing.py \
            --source-dir "$SOURCE_DIR" \
            --output-dir files/movie_data \
            --cache-dir files/tmdb_cache \
            --rate-limit 3.5

        if [ $? -eq 0 ]; then
            echo -e "\n${GREEN}✅ 数据预处理完成${NC}"
            echo -e "${GREEN}📁 输出文件位置: files/movie_data/${NC}\n"
        else
            echo -e "\n${RED}❌ 数据预处理失败${NC}\n"
            exit 1
        fi
    else
        echo -e "${YELLOW}⏭️  已跳过数据预处理步骤${NC}\n"
    fi
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}🎉 所有步骤执行完成！${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}📚 查看详细文档:${NC}"
echo -e "  - README:        data/movie/README.md"
echo -e "  - 设计文档:      docs/06-应用案例/电影推荐知识图谱设计文档.md"
echo ""
