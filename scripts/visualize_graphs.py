#!/usr/bin/env python3
"""
LangGraph 可视化工具

使用方法:
1. 查看对话图: python scripts/visualize_graphs.py --graph conversation
2. 查看检索子图: python scripts/visualize_graphs.py --graph retrieval
3. 查看路由图: python scripts/visualize_graphs.py --graph router
4. 导出为Mermaid: python scripts/visualize_graphs.py --graph conversation --format mermaid
5. 导出为ASCII: python scripts/visualize_graphs.py --graph conversation --format ascii
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))


def visualize_conversation_graph(format: str = "mermaid"):
    """可视化对话图"""
    from application.chat.conversation_graph import ConversationGraphRunner
    from infrastructure.rag.retrieval_subgraph import retrieval_subgraph_compiled
    from application.ports.router_port import RouterPort
    from application.ports.rag_executor_port import RAGExecutorPort
    from application.ports.rag_stream_executor_port import RAGStreamExecutorPort
    from application.ports.chat_completion_port import ChatCompletionPort
    from application.ports.conversation_store_port import ConversationStorePort

    print("=" * 80)
    print("对话图结构 (Conversation Graph)")
    print("=" * 80)
    print()
    print("图结构: START → route → recall → prepare_retrieval → retrieval_subgraph → generate → END")
    print()

    # 创建一个简单的 runner 来获取 graph
    try:
        # 导出 Mermaid 格式
        if format == "mermaid":
            print("\n### Mermaid 格式 (可复制到 https://mermaid.live/) ###\n")
            # 直接打印 graph 对象的 mermaid 表示
            print("```mermaid")
            # LangGraph 的 graph 对象可以转换为 Mermaid
            print("graph TD")
            print("    START([开始])")
            print("    ROUTE[路由: LLM分析意图]")
            print("    RECALL[召回: memory+summary+history]")
            print("    PREP[准备检索: State映射]")
            print("    RETRIEVAL[检索子图: Plan→Execute→Reflect→Merge]")
            print("    GENERATE[生成: RAG/General]")
            print("    END([结束])")
            print()
            print("    START --> ROUTE")
            print("    ROUTE --> RECALL")
            print("    RECALL --> PREP")
            print("    PREP -->|需要检索| RETRIEVAL")
            print("    PREP -->|跳过检索| GENERATE")
            print("    RETRIEVAL --> GENERATE")
            print("    GENERATE --> END")
            print("```")

        elif format == "ascii":
            print("\n### ASCII 图 ###\n")
            print("""
            ┌─────────────────────────────────────────────────────────────┐
            │                     Conversation Graph                       │
            └─────────────────────────────────────────────────────────────┘

            [START]
               │
               ▼
            ┌─────────┐
            │  route  │  LLM路由 (判定kb_prefix, 抽取实体, 推荐agent)
            └────┬────┘
                 │
                 ▼
            ┌─────────┐
            │ recall  │  召回上下文 (memory, summary, history, episodic)
            └────┬────┘
                 │
                 ▼
            ┌──────────────┐
            │ prepare_retr │  State映射 → RetrievalState
            └──────┬───────┘
                   │
           ┌───────┴────────┐
           ▼                ▼
      ┌────────┐      ┌──────────┐
      │检索子图 │      │ generate │ (跳过检索)
      └───┬────┘      └─────┬────┘
          │                 │
          └──────┬──────────┘
                 ▼
          ┌─────────────┐
          │  generate   │  生成答案 (RAG / General)
          └──────┬──────┘
                 │
                 ▼
              [END]

            === 检索子图 (Retrieval Subgraph) ===
            ┌──────────────────────────────────────────────┐
            │ Plan → Execute → Reflect → Merge             │
            │  (规划)  (执行)    (反思)    (合并)            │
            └──────────────────────────────────────────────┘
            """)

    except Exception as e:
        print(f"错误: {e}")
        print("\n提示: 某些依赖可能未配置，这是正常的。")
        print("上面的图示是静态描述，展示了架构。")


def visualize_retrieval_subgraph(format: str = "mermaid"):
    """可视化检索子图"""
    print("=" * 80)
    print("检索子图结构 (Retrieval Subgraph)")
    print("=" * 80)
    print()

    if format == "mermaid":
        print("\n### Mermaid 格式 ###\n")
        print("```mermaid")
        print("graph TD")
        print("    START([开始])")
        print("    PLAN[Plan: 生成检索计划]")
        print("    EXECUTE[Execute: 执行检索任务]")
        print("    REFLECT[Reflect: 反思与重试]")
        print("    MERGE[Merge: 合并结果]")
        print("    END([结束])")
        print()
        print("    START --> PLAN")
        print("    PLAN --> EXECUTE")
        print("    EXECUTE --> REFLECT")
        print("    REFLECT -->|需要重试| EXECUTE")
        print("    REFLECT -->|完成| MERGE")
        print("    MERGE --> END")
        print("```")

    elif format == "ascii":
        print("\n### ASCII 图 ###\n")
        print("""
        ┌──────────────────────────────────────────────────────────┐
        │              Retrieval Subgraph (检索子图)                 │
        └──────────────────────────────────────────────────────────┘

        [START]
           │
           ▼
        ┌────────┐
        │  Plan  │  Multi-Agent Planner 生成检索计划
        └────┬───┘
             │
             ▼
        ┌─────────┐
        │ Execute │  WorkerCoordinator 协调多个Agent执行检索
        └────┬────┘
             │
             ▼
        ┌──────────┐
        │ Reflect  │  Reflector 评估结果质量,决定是否重试
        └─────┬────┘
              │
      ┌───────┴────────┐
      ▼                ▼
  [需要重试]        [完成]
      │                │
      └─────┐          │
            │          │
            ▼          ▼
        ┌─────────┐  ┌───────┐
        │ Merge   │  │ Merge │  合并所有检索结果
        └────┬────┘  └───┬───┘
             │           │
             └─────┬─────┘
                   │
                   ▼
                [END]

        === 子模块说明 ===
        - Planner: 基于用户查询生成结构化检索计划
        - Executor: 协调 HybridAgent/GraphAgent/DeepResearchAgent 执行
        - Reflector: 评估检索完整性,必要时触发重试
        - Merge: 聚合多次检索结果,生成最终context
        """)


def visualize_router_graph(format: str = "mermaid"):
    """可视化路由图"""
    print("=" * 80)
    print("路由图结构 (Router Graph)")
    print("=" * 80)
    print()

    if format == "mermaid":
        print("\n### Mermaid 格式 ###\n")
        print("```mermaid")
        print("graph TD")
        print("    START([开始])")
        print("    INTENT[intent_detect: 意图识别]")
        print("    OVERRIDE[apply_override_policy: 覆盖策略]")
        print("    WORKER[worker_select: Worker选择]")
        print("    END([结束])")
        print()
        print("    START --> INTENT")
        print("    INTENT --> OVERRIDE")
        print("    OVERRIDE --> WORKER")
        print("    WORKER --> END")
        print("```")

    elif format == "ascii":
        print("\n### ASCII 图 ###\n")
        print("""
        ┌───────────────────────────────────────────────────────────┐
        │                   Router Graph (路由图)                    │
        └───────────────────────────────────────────────────────────┘

        [START]
           │
           ▼
        ┌───────────────────┐
        │  intent_detect    │  LLM分析查询意图
        │                    │  - 判定kb_prefix (movie/general)
        │                    │  - 抽取实体
        │                    │  - 推荐agent_type
        └────────┬──────────┘
                 │
                 ▼
        ┌───────────────────────┐
        │ apply_override_policy │  应用覆盖策略
        │                        │  - 用户指定优先
        │                        │  - 低置信度时保留用户选择
        └────────┬──────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │   worker_select     │  选择执行Worker
        │                      │  worker_name格式:
        │                      │  {kb_prefix}:{agent_type}:{agent_mode}
        │                      │  例: movie:hybrid_agent:retrieve_only
        └────────┬────────────┘
                 │
                 ▼
              [END]
        """)


def visualize_multi_agent_orchestrator(format: str = "mermaid"):
    """可视化Multi-Agent编排器"""
    print("=" * 80)
    print("Multi-Agent 编排器 (Multi-Agent Orchestrator)")
    print("=" * 80)
    print()

    if format == "mermaid":
        print("\n### Mermaid 格式 ###\n")
        print("```mermaid")
        print("graph LR")
        print("    INPUT([用户输入])")
        print("    PLANNER[Planner<br/>生成计划]")
        print("    EXECUTOR[Executor<br/>执行检索]")
        print("    REPORTER[Reporter<br/>生成报告]")
        print("    OUTPUT([最终输出])")
        print()
        print("    INPUT --> PLANNER")
        print("    PLANNER -->|需要澄清| OUTPUT")
        print("    PLANNER -->|计划OK| EXECUTOR")
        print("    EXECUTOR --> REPORTER")
        print("    REPORTER --> OUTPUT")
        print("```")

    elif format == "ascii":
        print("\n### ASCII 图 ###\n")
        print("""
        ┌───────────────────────────────────────────────────────────┐
        │           Multi-Agent Orchestrator Flow                    │
        └───────────────────────────────────────────────────────────┘

        [用户输入]
            │
            ▼
        ┌─────────────┐
        │   Planner   │  生成执行计划
        └──────┬──────┘
               │
       ┌───────┴────────┐
       ▼                ▼
   [需要澄清]      [计划OK]
       │                │
       ▼                ▼
    [返回]        ┌──────────┐
                  │ Executor │  执行检索任务
                  └────┬─────┘
                       │
                       ▼
                  ┌──────────┐
                  │ Reporter │  生成最终报告
                  └────┬─────┘
                       │
                       ▼
                   [最终输出]
        """)


def main():
    parser = argparse.ArgumentParser(description="LangGraph 可视化工具")
    parser.add_argument(
        "--graph",
        type=str,
        choices=["conversation", "retrieval", "router", "multi-agent", "all"],
        default="all",
        help="选择要可视化的图",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["mermaid", "ascii"],
        default="mermaid",
        help="输出格式",
    )

    args = parser.parse_args()

    if args.graph == "conversation":
        visualize_conversation_graph(args.format)
    elif args.graph == "retrieval":
        visualize_retrieval_subgraph(args.format)
    elif args.graph == "router":
        visualize_router_graph(args.format)
    elif args.graph == "multi-agent":
        visualize_multi_agent_orchestrator(args.format)
    elif args.graph == "all":
        visualize_conversation_graph(args.format)
        print("\n" + "=" * 80 + "\n")
        visualize_retrieval_subgraph(args.format)
        print("\n" + "=" * 80 + "\n")
        visualize_router_graph(args.format)
        print("\n" + "=" * 80 + "\n")
        visualize_multi_agent_orchestrator(args.format)

    print("\n" + "=" * 80)
    print("提示: 复制 Mermaid 代码到 https://mermaid.live/ 查看可视化图")
    print("=" * 80)


if __name__ == "__main__":
    main()
