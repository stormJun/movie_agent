"""
用户反馈处理服务。

该模块提供了 FeedbackService 类，用于管理用户对 AI 回答的反馈（点赞/点踩）。
作为应用层服务，将持久化和处理逻辑委托给端口实现，遵循六边形架构模式。
"""

from __future__ import annotations

from typing import Dict

from application.ports.feedback_port import FeedbackPort


class FeedbackService:
    """处理用户对 AI 回答反馈的服务。

    该服务作为 API 层和基础设施层之间的中介，处理与反馈收集相关的
    业务逻辑，并将存储委托给后端实现。

    服务遵循依赖倒置原则，依赖于 FeedbackPort 抽象而非具体实现。

    Attributes:
        _port: 处理实际反馈存储和处理逻辑的端口实现
               （例如：数据库持久化）

    Example:
        创建服务实例并调用异步方法：
        >>> port = PostgresFeedbackPort(db_connection)
        >>> service = FeedbackService(port=port)
        >>> # 在异步函数中调用
        >>> # result = await service.process_feedback(
        >>> #     message_id="msg_123",
        >>> #     query="推荐一些科幻电影",
        >>> #     is_positive=True,
        >>> #     thread_id="thread_456"
        >>> # )
    """

    def __init__(self, *, port: FeedbackPort) -> None:
        """使用端口实现初始化反馈服务。

        Args:
            port: 实现 FeedbackPort 接口的具体实现，负责实际的
                  反馈数据持久化和处理

        Raises:
            TypeError: 如果 port 没有实现 FeedbackPort 接口
        """
        self._port = port

    async def process_feedback(
        self,
        *,
        message_id: str,
        query: str,
        is_positive: bool,
        thread_id: str,
        agent_type: str = "graph_agent",
        request_id: str | None = None,
    ) -> Dict[str, str]:
        """处理并存储用户对 AI 回答的反馈。

        该方法接收用户反馈（正面或负面），并委托给端口实现进行存储。
        收集的反馈可用于多种用途，包括：

        - 强化学习优化模型
        - 个性化推荐调整
        - 检索质量评估
        - A/B 测试和评估
        - 数据分析和监控

        Args:
            message_id: 被反馈的 AI 消息的唯一标识符
            query: 触发 AI 回答的原始用户查询
            is_positive: True 为点赞，False 为点踩
            thread_id: 会话线程 ID，用于关联相关反馈
            agent_type: 生成响应的 Agent 类型
                       （默认："graph_agent"）
            request_id: 可选的请求 ID，用于追踪和日志记录

        Returns:
            包含处理结果的字典，通常包含 'status' 字段表示成功或失败

        Raises:
            ValueError: 如果任何必需参数无效或缺失
            ConnectionError: 如果无法连接到存储后端
            Timeout: 如果存储操作超时

        Example:
            在异步上下文中调用：
            >>> # async def handle():
            >>> #     result = await service.process_feedback(
            >>> #         message_id="msg_abc123",
            >>> #         query="有什么好的动作片推荐吗？",
            >>> #         is_positive=True,
            >>> #         thread_id="conv_xyz789",
            >>> #         agent_type="graph_agent"
            >>> #     )
            >>> #     return result
        """
        # 委托给端口实现进行实际存储
        return await self._port.process_feedback(
            message_id=message_id,
            query=query,
            is_positive=is_positive,
            thread_id=thread_id,
            agent_type=agent_type,
            request_id=request_id,
        )
