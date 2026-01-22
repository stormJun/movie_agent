import uvicorn
from fastapi import FastAPI
from server.api_router import api_router
from config.database import get_db_manager, has_db_manager
from config.settings import UVICORN_CONFIG
from infrastructure.agents.rag_factory import rag_agent_manager as agent_manager
from infrastructure.bootstrap import bootstrap_core_ports
from server.api.rest.dependencies import shutdown_dependencies

bootstrap_core_ports()

# 初始化 FastAPI 应用
app = FastAPI(title="知识图谱问答系统", description="基于知识图谱的智能问答系统后端API")

# 添加路由
app.include_router(api_router)

# 获取数据库连接（延迟初始化）
driver = None


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    await shutdown_dependencies()
    # 关闭所有Agent资源
    agent_manager.close_all()
    
    # 关闭Neo4j连接
    if has_db_manager():
        db_manager = get_db_manager()
        driver = getattr(db_manager, "driver", None)
        if driver:
            driver.close()
            print("已关闭Neo4j连接")


# 启动服务器
if __name__ == "__main__":
    uvicorn.run("server.main:app", **UVICORN_CONFIG)
