import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import asyncio
import json
from graphrag_agent.agents.deep_research_agent import DeepResearchAgent
from infrastructure.bootstrap import bootstrap_core_ports

bootstrap_core_ports()

# DeepResearchAgent 综合测试
async def test_deep_research_agent_advanced():
    print("\n======= DeepResearchAgent 高级功能测试 =======")
    agent = DeepResearchAgent(use_deeper_tool=True)
    
    # 1. 基本流式输出测试 (不显示思考过程)
    print("\n--- 基本流式输出测试 ---")
    trace = agent.retrieve_with_trace("优秀学生要如何申请", thread_id="test")
    print(trace.get("context", ""))
    
    # 2. 显示思考过程的流式输出
    print("\n\n--- 思考过程可见模式 ---")
    trace = agent.retrieve_with_trace("优秀学生要如何申请", thread_id="test-thinking")
    print(trace.get("context", ""))
            
    # 3. 知识图谱探索功能测试
    print("\n\n--- 知识图谱探索功能 ---")
    exploration_result = agent.explore_knowledge("华东理工大学奖学金体系")
    print("\n知识图谱探索结果摘要:")
    if isinstance(exploration_result, dict):
        if "error" in exploration_result:
            print(f"错误: {exploration_result['error']}")
        else:
            print(f"探索路径: {len(exploration_result.get('exploration_path', []))} 步")
            print(f"发现实体: {exploration_result.get('discovered_entities', [])[:3]}")
            print(f"摘要: {exploration_result.get('summary', '')[:200]}...")
    else:
        print(exploration_result)
    
    # v3 strict: deep thinking / reasoning analysis are service-side responsibilities.
    
    # v3 strict: contradictions/analysis are removed from agent.
    
    # v3 strict: community-aware enhancement is service-side.
    
    # 7. 不同配置参数测试（仅检索）
    print("\n\n--- 不同配置参数测试（仅检索） ---")
    trace = agent.retrieve_with_trace("奖学金申请流程简介", thread_id="test-config")
    print(trace.get("context", "")[:300] + "...")
    
    # 8. 工具比较测试：由服务侧决定检索策略（agent 内不再切换）

async def run_advanced_tests():
    await test_deep_research_agent_advanced()

if __name__ == "__main__":
    asyncio.run(run_advanced_tests())
