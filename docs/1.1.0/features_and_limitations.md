# GraphRAG Agent v1.1.0 特性与限制说明

本文档主要说明 v1.1.0 版本中“调试模式”的功能定义、使用场景及其当前的已知限制。

## 调试模式 (Debug Mode)

前段界面上的“调试模式（关闭流式）”选项主要服务于开发和排查目的。

### 核心行为

开启“调试模式”后，系统将发生以下变化：

1.  **通信协议变更**：
    *   **正常模式**：使用 SSE (Server-Sent Events) 流式传输。前端逐字显示回复，并实时展示推理过程（Thinking）、检索步骤（Retrieval）等中间状态。
    *   **调试模式**：使用标准 HTTP POST 请求。前端会等待后端完全处理完毕后，一次性接收并展示所有结果。

2.  **响应数据结构**：
    *   调试模式下，后端 `/api/v1/chat` 接口返回完整的 JSON 结构，包含 `answer`, `execution_log`, `kg_data`, `retrieval_results` 等详细字段。
    *   这便于开发者通过浏览器 Network 面板直接查看原始数据，检查字段是否完整、JSON 格式是否正确。

### 适用场景

*   **API 调试**：当遇到流式输出乱码、截断或无法解析时，使用调试模式可排查是否为后端数据问题。
*   **性能分析**：想要获取一次请求的完整耗时而不受网络流式传输影响时。
*   **结构验证**：验证 RagRunResult 或 KnowledgeGraph 等复杂对象的序列化结果。

### 已知限制 (Known Issues)

**Deep Research Agent 推理过程缺失**

*   **现象**：在使用 **Deep Research Agent** 时，如果开启“调试模式”，前端将**无法显示**推理过程（Thinking）日志，虽然最终的回答（Answer）是正常的。
*   **原因**：
    *   Deep Research Agent 产生大量的中间状态（搜索、阅读、思考），这些状态在“流式模式”下是通过 SSE 事件实时推送的。
    *   在目前的“非流式模式”实现中，后端 `ChatHandler` 仅聚合了最终结果，**未收集**流式执行器（Stream Executor）产生的中间 `thinking` 事件。
    *   因此，非流式响应的 JSON 中缺失了 `raw_thinking` 或 `iterations` 等字段。
*   **规避方案**：
    *   如果您需要查看 Deep Research Agent 的详细思考和检索过程，请**关闭调试模式**，使用默认的流式输出（SSE）。

### 解决方案 (Proposed Solution)

为解决上述 Deep Research Agent 在调试模式下信息缺失的问题，建议后端进行以下改造：

1.  **修改 ChatHandler**：
    *   在 `ChatHandler.handle` 方法中，对于 Deep Research Agent，不应简单等待最终结果。
    *   应使用 `collect_events` 机制，在服务器端消费并缓存 `StreamExecutor` 产生的所有 SSE 事件。
2.  **聚合日志**：
    *   遍历收集到的事件，提取所有 `thinking` 类型的事件内容，拼接为完整的 `raw_thinking` 字符串。
    *   提取 `retrieval` 类型的事件，聚合为检索可观察性数据。
3.  **增强 ChatResponse**：
    *   将聚合后的 `raw_thinking` 和其他中间状态字段添加到 `ChatResponse` 以及最终返回的 JSON 中。

通过上述改造，调试模式的响应体将包含与流式模式等同的丰富信息，从而不仅能调试“结果”，也能离线调试“过程”。
