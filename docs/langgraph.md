# LangGraph

## 目录

- 1. 简介
- 2. 版本与安装
- 3. 学习路线（最小路径）
- 4. 与 AutoGen 对比
- 5. 适用场景
- 6. 基本概念与 State 设计
- 7. 运行方式与事件
- 8. 子图与 First-Class Subgraph
- 9. Checkpointer / 记忆
- 10. 错误处理与重试
- 11. 性能与工程化
- 12. 调试与观测
- 13. 常见坑
- 14. 示例：langgraph_hello.py
- 15. 参考

## 1. 简介

LangGraph 是一个用于构建具有 LLM 的**有状态、多角色**应用的图式编排库，常用于代理（Agent）与多代理工作流。

## 2. 版本与安装

- 版本：按你项目的依赖锁定即可（示例：`langgraph==0.3.x`）
- 最小安装：`pip install langgraph==<version>`

## 3. 学习路线（最小路径）

建议按“最小可运行图 → 条件分支 → 工具调用 → 子图 → 流式 → 记忆”的顺序练习：

1) 最小图：一个节点 + 直通边，跑通 `invoke`。
2) 条件边：用 `add_conditional_edges` 分支路由。
3) 工具调用：ToolNode + should_continue。
4) 子图：把一个子流程独立成 subgraph。
5) 流式：`astream` + `stream_mode` + 自定义事件。
6) 记忆：加 checkpointer 与 `thread_id`。

## 4. 与 AutoGen 对比

| 维度 | AutoGen | LangGraph |
| --- | --- | --- |
| 协作模式 | 对话驱动，模拟人类团队讨论 | 图结构驱动，节点定义逻辑，边定义流程顺序 |
| 状态管理 | 会话历史维护上下文，默认不持久化 | 内置持久化引擎（MemorySaver） |
| 工具链集成 | 强调与 LLM 和代码工具的深度整合 | 兼容 LangChain 工具链，支持多模态输入 |

## 5. 适用场景

- 选 AutoGen：快速实现人机协作自动化（如代码生成 + 人工审核）
- 选 LangGraph：复杂状态系统（如多级审核、可循环流程）
- 混合使用：LangGraph 编排全局流程，AutoGen 处理子任务

## 6. 基本概念与 State 设计

- State：共享数据快照（TypedDict 或 Pydantic BaseModel）。
- Nodes：节点函数，输入 State，返回更新字段。
- Edges：边，决定下一步节点（条件分支/固定转换）。

State 设计细节：
- TypedDict：轻量、运行时不校验；适合大多数状态机场景。
- Pydantic BaseModel：有运行时校验/默认值，适合强约束输入输出，但序列化成本更高。
- reducer（如 `add_messages`）：用于“追加式”合并，而非覆盖；适合消息列表累加。
- 注意：**节点名不能与 state key 冲突**，否则会触发 LangGraph channel 冲突错误。

底层模型：LangGraph 的图执行借鉴了 Google Pregel 的“顶点中心计算”模型，使用消息传递与 BSP（批量同步并行）驱动状态流转。

## 7. 运行方式与事件

- `invoke`：同步调用，返回最终 state。
- `ainvoke`：异步调用，适合并发/IO 密集场景。
- `astream`：异步流式输出（token/自定义事件）。
- `stream_mode="custom"`：仅输出 writer 写入的自定义事件；常见 payload 为 dict。
- `subgraphs=True`：子图事件以 `(namespace, payload)` 或 `(namespace, mode, payload)` 冒泡。

## 8. 子图与 First-Class Subgraph

- 子图是一个完整的 StateGraph，可当作主图节点挂载。
- 主图 `add_node("subgraph", subgraph)` 后，LangGraph Studio 可展开子图结构。
- 事件冒泡：主图流式需 `subgraphs=True`，再在上层统一解包 `(ns, payload)`。

## 9. Checkpointer / 记忆

- `MemorySaver`：内存级持久化，适合本地开发/短会话。
- `RedisSaver` / `PostgresSaver`：可共享/可恢复，适合线上。
- `thread_id`：同一会话的稳定标识；不变即可复用历史状态。
- 生命周期：`thread_id` 改变即新会话；旧 state 不再自动关联。

## 10. 错误处理与重试

- 节点内部建议捕获异常并返回 error 字段，避免整图失败。
- 超时与重试：可通过业务层预算参数控制（如 timeout_s / max_retries）。
- 递归/迭代上限：使用 `recursion_limit` 或子图内的 `max_iterations` 防止死循环。

## 11. 性能与工程化

- 并发与限流：控制同时执行的节点数或外部调用并发。
- 长任务：避免超时导致图被取消；必要时拆分为子图或异步任务。
- 状态体积：大对象用摘要；避免把原始大文本直接写入 state。
- 事件节流：流式输出过密时合并片段或降低频率。

## 12. 调试与观测

- LangGraph Studio：可视化主图/子图结构与执行路径。
- Langfuse/Trace：在 HTTP 层建立 root trace，绑定下游 LangGraph span。
- 自定义日志节点：常用 `writer({"execution_log": {...}})` 输出结构化日志。

## 13. 常见坑

- 状态可变对象被原地修改：应返回新的 dict/列表，避免隐式共享。
- 返回全量 state 导致覆盖：节点只应返回“更新字段”。
- 消息重复追加：未用 reducer 或多次追加同一消息。
- 边条件不一致：条件边与节点输出字段不匹配，导致走错分支或死路。

## 14. 示例：langgraph_hello.py

```
#示例：langgraph_hello.py
from typing import Literal
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
# pip install langgraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, MessagesState
from langgraph.prebuilt import ToolNode

# 定义工具函数，用于代理调用外部工具
@tool
def search(query: str):
    """模拟一个搜索工具"""
    if "上海" in query.lower() or "Shanghai" in query.lower():
        return "现在30度，有雾."
    return "现在是35度，阳光明媚。"


# 将工具函数放入工具列表
tools = [search]

# 创建工具节点
tool_node = ToolNode(tools)

# 1.初始化模型和工具，定义并绑定工具到模型
model = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(tools)

# 定义函数，决定是否继续执行
def should_continue(state: MessagesState) -> Literal["tools", END]:
    messages = state['messages']
    last_message = messages[-1]
    # 如果LLM调用了工具，则转到“tools”节点
    if last_message.tool_calls:
        return "tools"
    # 否则，停止（回复用户）
    return END


# 定义调用模型的函数
def call_model(state: MessagesState):
    messages = state['messages']
    response = model.invoke(messages)
    # 返回列表，因为这将被添加到现有列表中
    return {"messages": [response]}

# 2.用状态初始化图，定义一个新的状态图
workflow = StateGraph(MessagesState)
# 3.定义图节点，定义我们将循环的两个节点
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

# 4.定义入口点和图边
# 设置入口点为“agent”
# 这意味着这是第一个被调用的节点
workflow.set_entry_point("agent")

# 添加条件边
workflow.add_conditional_edges(
    # 首先，定义起始节点。我们使用`agent`。
    # 这意味着这些边是在调用`agent`节点后采取的。
    "agent",
    # 接下来，传递决定下一个调用节点的函数。
    should_continue,
)

# 添加从`tools`到`agent`的普通边。
# 这意味着在调用`tools`后，接下来调用`agent`节点。
workflow.add_edge("tools", 'agent')

# 初始化内存以在图运行之间持久化状态
checkpointer = MemorySaver()

# 5.编译图
# 这将其编译成一个LangChain可运行对象，
# 这意味着你可以像使用其他可运行对象一样使用它。
# 注意，我们（可选地）在编译图时传递内存
app = workflow.compile(checkpointer=checkpointer)

# 6.执行图，使用可运行对象
final_state = app.invoke(
    {"messages": [HumanMessage(content="上海的天气怎么样?")]},
    config={"configurable": {"thread_id": 42}}
)
# 从 final_state 中获取最后一条消息的内容
result = final_state["messages"][-1].content
print(result)
final_state = app.invoke(
    {"messages": [HumanMessage(content="我问的那个城市?")]},
    config={"configurable": {"thread_id": 42}}
)
result = final_state["messages"][-1].content
print(result)
```

## 15. 参考

- 官方文档：https://langchain-ai.github.io/langgraph/
