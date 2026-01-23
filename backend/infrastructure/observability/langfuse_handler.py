"""Langfuse 集成模块

提供 LLM 调用的可观测性和追踪功能。
"""

from __future__ import annotations

import os
from functools import wraps
from typing import Any, AsyncGenerator, Callable

from dotenv import load_dotenv
from langfuse import Langfuse
from langfuse.decorators import observe

# 确保加载 .env 文件
load_dotenv(override=True)

# === 配置 ===
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() in ("true", "1", "yes")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

# === 全局 Langfuse 客户端 ===
_langfuse_client: Langfuse | None = None


def _get_langfuse_client() -> Langfuse | None:
    """获取 Langfuse 客户端（单例）

    Returns:
        Langfuse 客户端实例，如果未启用则返回 None
    """
    global _langfuse_client

    if not LANGFUSE_ENABLED:
        return None

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        return None

    if _langfuse_client is None:
        _langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )

    return _langfuse_client


def langfuse_observe(
    name: str | None = None,
    capture_input: bool = True,
    capture_output: bool = True,
):
    """Langfuse 追踪装饰器

    用于装饰需要追踪的函数，自动记录调用链

    Args:
        name: 追踪名称（默认使用函数名）
        capture_input: 是否捕获输入
        capture_output: 是否捕获输出

    Returns:
        装饰器函数
    """
    if not LANGFUSE_ENABLED:
        # 如果未启用，返回无操作装饰器
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    # 使用 Langfuse 的 observe 装饰器
    return observe(
        name=name,
        capture_input=capture_input,
        capture_output=capture_output,
    )


async def flush_langfuse():
    """刷新 Langfuse 缓冲区，确保所有数据都发送到服务器

    建议在应用关闭时调用
    """
    client = _get_langfuse_client()
    if client:
        await client.flush_async()


def create_langfuse_session(
    session_id: str,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建 Langfuse 会话

    Args:
        session_id: 会话 ID
        user_id: 用户 ID（可选）
        metadata: 额外的元数据（可选）

    Returns:
        会话信息字典
    """
    if not LANGFUSE_ENABLED:
        return {"session_id": session_id}

    return {
        "session_id": session_id,
        "user_id": user_id,
        "metadata": metadata or {},
    }


__all__ = [
    "LANGFUSE_ENABLED",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
    "_get_langfuse_client",
    "get_langfuse_async_openai",
    "langfuse_observe",
    "flush_langfuse",
    "create_langfuse_session",
]
