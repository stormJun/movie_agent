"""
测试路由 LLM 自动推荐 agent_type 的功能

运行测试：
    python test/test_router_agent_recommendation.py
"""

import asyncio
from infrastructure.routing.kb_router.router import route_kb_prefix


def test_simple_qa_recommendation():
    """测试简单事实查询 → 应该推荐 graph_agent"""
    message = "喜宴哪一年上映？"

    kb_prefix, result = route_kb_prefix(message)

    print("=" * 60)
    print(f"查询：{message}")
    print("=" * 60)
    print(f"知识库：{kb_prefix}")
    print(f"推荐 Agent：{result.recommended_agent_type}")
    print(f"查询意图：{result.query_intent}")
    print(f"推理原因：{result.reason}")
    print(f"置信度：{result.confidence}")
    print()

    # 验证：简单事实查询应该推荐 graph_agent
    assert result.recommended_agent_type == "graph_agent", \
        f"简单事实查询应该推荐 graph_agent，但推荐了 {result.recommended_agent_type}"
    assert result.query_intent == "qa", \
        f"查询意图应该是 qa，但是 {result.query_intent}"


def test_analytical_qa_recommendation():
    """测试分析性查询 → 应该推荐 hybrid_agent"""
    message = "李安的导演风格是怎样的？"

    kb_prefix, result = route_kb_prefix(message)

    print("=" * 60)
    print(f"查询：{message}")
    print("=" * 60)
    print(f"知识库：{kb_prefix}")
    print(f"推荐 Agent：{result.recommended_agent_type}")
    print(f"查询意图：{result.query_intent}")
    print(f"推理原因：{result.reason}")
    print(f"置信度：{result.confidence}")
    print()

    # 验证：分析性查询应该推荐 hybrid_agent
    assert result.recommended_agent_type == "hybrid_agent", \
        f"分析性查询应该推荐 hybrid_agent，但推荐了 {result.recommended_agent_type}"
    assert result.query_intent == "qa", \
        f"查询意图应该是 qa，但是 {result.query_intent}"


def test_recommendation_query_recommendation():
    """测试推荐查询 → 应该推荐 fusion_agent"""
    message = "推荐几部类似《喜宴》的电影"

    kb_prefix, result = route_kb_prefix(message)

    print("=" * 60)
    print(f"查询：{message}")
    print("=" * 60)
    print(f"知识库：{kb_prefix}")
    print(f"推荐 Agent：{result.recommended_agent_type}")
    print(f"查询意图：{result.query_intent}")
    print(f"推理原因：{result.reason}")
    print(f"置信度：{result.confidence}")
    print()

    # 验证：推荐查询应该推荐 fusion_agent
    assert result.recommended_agent_type == "fusion_agent", \
        f"推荐查询应该推荐 fusion_agent，但推荐了 {result.recommended_agent_type}"
    assert result.query_intent == "recommend", \
        f"查询意图应该是 recommend，但是 {result.query_intent}"


def test_compare_query_recommendation():
    """测试比较查询 → 应该推荐 fusion_agent"""
    message = "对比一下《喜宴》和《饮食男女》的风格差异"

    kb_prefix, result = route_kb_prefix(message)

    print("=" * 60)
    print(f"查询：{message}")
    print("=" * 60)
    print(f"知识库：{kb_prefix}")
    print(f"推荐 Agent：{result.recommended_agent_type}")
    print(f"查询意图：{result.query_intent}")
    print(f"推理原因：{result.reason}")
    print(f"置信度：{result.confidence}")
    print()

    # 验证：比较查询应该推荐 fusion_agent
    assert result.recommended_agent_type == "fusion_agent", \
        f"比较查询应该推荐 fusion_agent，但推荐了 {result.recommended_agent_type}"
    assert result.query_intent == "compare", \
        f"查询意图应该是 compare，但是 {result.query_intent}"


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("测试路由 LLM 自动推荐 agent_type 功能")
    print("=" * 60 + "\n")

    try:
        # 测试 1：简单事实查询
        print("\n【测试 1】简单事实查询")
        test_simple_qa_recommendation()
        print("✅ 测试通过\n")

        # 测试 2：分析性查询
        print("\n【测试 2】分析性查询")
        test_analytical_qa_recommendation()
        print("✅ 测试通过\n")

        # 测试 3：推荐查询
        print("\n【测试 3】推荐查询")
        test_recommendation_query_recommendation()
        print("✅ 测试通过\n")

        # 测试 4：比较查询
        print("\n【测试 4】比较查询")
        test_compare_query_recommendation()
        print("✅ 测试通过\n")

        print("=" * 60)
        print("🎉 所有测试通过！路由 LLM 智能推荐功能正常工作")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n❌ 测试失败：{e}")
        print("\n提示：如果 LLM 返回的 agent_type 不符合预期，可能需要：")
        print("1. 检查路由 Prompt 是否足够清晰")
        print("2. 调整 LLM 模型（建议使用更强的模型，如 GPT-4）")
        print("3. 增加示例数量帮助 LLM 理解")
    except Exception as e:
        print(f"\n❌ 发生错误：{e}")
        import traceback
        traceback.print_exc()
