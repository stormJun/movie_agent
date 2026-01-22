"""
聊天处理器

本模块实现了聊天请求的核心处理流程，包括：
1. 路由决策：根据用户消息和会话上下文决定使用哪个知识库和代理类型
2. 记忆管理：可选的长期记忆服务，用于跨会话的上下文记忆
3. 多种执行模式：
   - 知识库处理器模式：通过KB Handler处理特定知识库的请求
   - 纯对话模式：不使用检索，直接通过LLM生成回复
   - RAG模式：使用检索增强生成，结合知识图谱和向量检索
4. 会话持久化：保存对话历史到存储层
"""

from __future__ import annotations

from typing import Any, Optional

from application.handlers.factory import KnowledgeBaseHandlerFactory
from application.chat.memory_service import MemoryService
from application.ports.chat_completion_port import ChatCompletionPort
from application.ports.conversation_store_port import ConversationStorePort
from application.ports.rag_executor_port import RAGExecutorPort
from application.ports.router_port import RouterPort
from domain.chat.entities.rag_run import RagRunSpec


def _resolve_agent_type(*, agent_type: str, worker_name: str) -> str:
    """
    解析实际的代理类型

    支持从 worker_name 中提取代理类型，worker_name 格式为：
    v1: "{agent_type}"
    v2: "{kb_prefix}:{agent_type}:{agent_mode}"

    Args:
        agent_type: 默认代理类型（当无法从 worker_name 解析时使用）
        worker_name: 工作名称字符串，可能包含代理类型信息

    Returns:
        解析后的代理类型字符串
    """
    raw = (worker_name or "").strip()
    if not raw:
        return agent_type
    parts = [p.strip() for p in raw.split(":")]
    # worker_name v2: {kb_prefix}:{agent_type}:{agent_mode}
    if len(parts) >= 2:
        candidate = parts[1]
        return candidate or agent_type
    return raw


class ChatHandler:
    """
    聊天处理器

    负责处理用户聊天请求的核心业务逻辑，包括路由决策、检索、生成和会话管理。
    支持三种处理模式：
    1. KB Handler 模式：使用知识库专用处理器（需要启用 enable_kb_handlers）
    2. 纯对话模式：不使用检索，直接通过LLM生成回复（general KB）
    3. RAG 模式：使用知识图谱和向量检索进行增强生成
    """
    def __init__(
        self,
        *,
        router: RouterPort,
        executor: RAGExecutorPort,
        completion: ChatCompletionPort,
        conversation_store: ConversationStorePort,
        memory_service: MemoryService | None = None,
        kb_handler_factory: Optional[KnowledgeBaseHandlerFactory] = None,
        enable_kb_handlers: bool = False,
    ) -> None:
        """
        初始化聊天处理器

        Args:
            router: 路由端口，用于决定使用哪个知识库和代理类型
            executor: RAG执行器端口，用于执行检索增强生成
            completion: 聊天补全端口，用于纯对话模式的LLM生成
            conversation_store: 会话存储端口，用于持久化对话历史
            memory_service: 可选的长期记忆服务，用于跨会话的上下文记忆
            kb_handler_factory: 可选的知识库处理器工厂，用于KB Handler模式
            enable_kb_handlers: 是否启用KB Handler模式
        """
        self._router = router
        self._executor = executor
        self._completion = completion
        self._conversation_store = conversation_store
        self._memory_service = memory_service
        self._kb_handler_factory = kb_handler_factory
        self._enable_kb_handlers = enable_kb_handlers

    async def handle(
        self,
        *,
        user_id: str,
        message: str,
        session_id: str,
        kb_prefix: Optional[str] = None,
        debug: bool = False,
        agent_type: str = "hybrid_agent",
    ) -> dict[str, Any]:
        """
        处理用户聊天请求

        处理流程：
        1. 获取或创建会话ID，并保存用户消息
        2. 路由决策：根据消息内容和会话上下文决定使用哪个知识库和代理
        3. 记忆召回：如果启用了记忆服务，召回相关的历史上下文
        4. 根据路由决策选择执行模式：
           - KB Handler模式：使用知识库专用处理器
           - 纯对话模式：直接通过LLM生成回复
           - RAG模式：执行检索增强生成
        5. 保存助手回复到会话历史
        6. 可选地将对话写入长期记忆

        Args:
            user_id: 用户ID
            message: 用户消息内容
            session_id: 会话ID
            kb_prefix: 可选的知识库前缀，用于覆盖路由决策
            debug: 是否启用调试模式（返回详细的检索和路由信息）
            agent_type: 默认的代理类型（hybrid_agent, graph_agent, deep_research_agent等）

        Returns:
            包含回复内容的字典，可能包含以下字段：
            - answer: 助手回复内容
            - reference: 参考文献/引用（仅在debug模式或RAG模式下）
            - retrieval_results: 检索结果（仅在RAG模式下）
            - debug: 是否为调试模式
            - route_decision: 路由决策详情（仅在debug模式下）
            - rag_runs: RAG执行记录（仅在debug模式下的RAG模式中）
        """
        # 1. 获取或创建会话ID，并保存用户消息
        conversation_id = await self._conversation_store.get_or_create_conversation_id(
            user_id=user_id,
            session_id=session_id,
        )
        await self._conversation_store.append_message(
            conversation_id=conversation_id,
            role="user",
            content=message,
        )

        # 2. 路由决策：决定使用哪个知识库和代理类型
        decision = self._router.route(
            message=message,
            session_id=session_id,
            requested_kb=kb_prefix,
            agent_type=agent_type,
        )
        resolved_agent_type = _resolve_agent_type(
            agent_type=agent_type,
            worker_name=decision.worker_name,
        )
        use_retrieval = (decision.kb_prefix or "").strip() not in {"", "general"}

        # 3. 记忆召回：从长期记忆中检索相关上下文
        memory_context: str | None = None
        if self._memory_service is not None:
            memory_context = await self._memory_service.recall_context(
                user_id=user_id,
                query=message,
            )

        # 4.1 KB Handler模式：使用知识库专用处理器处理请求
        if self._enable_kb_handlers and self._kb_handler_factory is not None:
            kb_handler = self._kb_handler_factory.get(decision.kb_prefix)
            if kb_handler is not None:
                response = await kb_handler.process(
                    message=message,
                    session_id=session_id,
                    agent_type=resolved_agent_type,
                    debug=debug,
                    memory_context=memory_context,
                )
                # 持久化助手回复（如果有）
                answer = str(response.get("answer") or "")
                if answer:
                    await self._conversation_store.append_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=answer,
                        citations=response.get("reference") if debug else None,
                        debug={"route_decision": decision.__dict__} if debug else None,
                    )
                    # 将对话写入长期记忆
                    if self._memory_service is not None:
                        await self._memory_service.maybe_write(
                            user_id=user_id,
                            user_message=message,
                            assistant_message=answer,
                            metadata={"session_id": session_id, "kb_prefix": decision.kb_prefix},
                        )
                response["debug"] = debug
                if debug:
                    response["route_decision"] = decision.__dict__
                return response

        # 4.2 纯对话模式：不使用检索，直接通过LLM生成回复
        if not use_retrieval:
            answer = await self._completion.generate(
                message=message,
                memory_context=memory_context,
            )
            if answer:
                await self._conversation_store.append_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer,
                )
                # 将对话写入长期记忆
                if self._memory_service is not None:
                    await self._memory_service.maybe_write(
                        user_id=user_id,
                        user_message=message,
                        assistant_message=answer,
                        metadata={"session_id": session_id, "kb_prefix": decision.kb_prefix},
                    )
            response: dict[str, Any] = {"answer": answer, "debug": debug}
            if debug:
                response["route_decision"] = decision.__dict__
            return response

        # 4.3 RAG模式：使用检索增强生成
        # 构建RAG执行计划
        plan = [
            RagRunSpec(
                agent_type=resolved_agent_type,
                worker_name=decision.worker_name,
            )
        ]
        # 执行RAG检索和生成
        aggregated, runs = await self._executor.run(
            plan=plan,
            message=message,
            session_id=session_id,
            kb_prefix=decision.kb_prefix,
            debug=debug,
            memory_context=memory_context,
        )

        # 5. 持久化助手回复
        if aggregated.answer:
            await self._conversation_store.append_message(
                conversation_id=conversation_id,
                role="assistant",
                content=aggregated.answer,
                citations=aggregated.reference if debug else None,
                debug={"rag_runs": [run.__dict__ for run in runs]} if debug else None,
            )
            # 将对话写入长期记忆
            if self._memory_service is not None:
                await self._memory_service.maybe_write(
                    user_id=user_id,
                    user_message=message,
                    assistant_message=aggregated.answer,
                    metadata={"session_id": session_id, "kb_prefix": decision.kb_prefix},
                )

        # 6. 构建响应
        response: dict[str, Any] = {"answer": aggregated.answer}
        response["debug"] = debug
        if aggregated.reference:
            response["reference"] = aggregated.reference
        if aggregated.retrieval_results is not None:
            response["retrieval_results"] = aggregated.retrieval_results
        if debug:
            response["rag_runs"] = [run.__dict__ for run in runs]
            response["route_decision"] = decision.__dict__
        return response
