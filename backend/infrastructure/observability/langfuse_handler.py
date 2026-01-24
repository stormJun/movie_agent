"""Langfuse 集成模块

提供 LLM 调用的可观测性和追踪功能。
"""

from __future__ import annotations

import contextvars
import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator

from langfuse import Langfuse
from langfuse.decorators import observe
from langfuse.callback import CallbackHandler
from langfuse.client import StatefulSpanClient, StatefulTraceClient

# === 配置 ===
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "false").lower() in ("true", "1", "yes")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

# === 全局 Langfuse 客户端 ===
_langfuse_client: Langfuse | None = None


StatefulClient = StatefulTraceClient | StatefulSpanClient

# Per-request context to avoid trace splitting. This propagates across asyncio
# tasks by default, but does NOT propagate into asyncio.to_thread.
_stateful_client_var: contextvars.ContextVar[StatefulClient | None] = contextvars.ContextVar(
    "langfuse_stateful_client",
    default=None,
)
_user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "langfuse_user_id",
    default=None,
)
_session_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "langfuse_session_id",
    default=None,
)


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


def get_current_langfuse_stateful_client() -> StatefulClient | None:
    return _stateful_client_var.get()


@contextmanager
def use_langfuse_request_context(
    *,
    stateful_client: StatefulClient | None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Iterator[None]:
    """Bind current asyncio context to an existing Langfuse trace/span.

    In this repo, the HTTP layer creates the root trace. Downstream code should
    attach spans/generations to that trace to avoid "trace splitting".
    """

    token_client = _stateful_client_var.set(stateful_client)
    token_user = _user_id_var.set(user_id)
    token_session = _session_id_var.set(session_id)
    try:
        yield
    finally:
        _stateful_client_var.reset(token_client)
        _user_id_var.reset(token_user)
        _session_id_var.reset(token_session)


@contextmanager
def use_langfuse_stateful_client(stateful_client: StatefulClient | None) -> Iterator[None]:
    """Temporarily override the active stateful client (trace/span) in this task."""
    token_client = _stateful_client_var.set(stateful_client)
    try:
        yield
    finally:
        _stateful_client_var.reset(token_client)


def get_langfuse_callback(
    *,
    stateful_client: StatefulClient | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> CallbackHandler | None:
    """获取 Langfuse LangChain Callback Handler

    用于传递给 LangChain 的 callbacks 参数，以捕捉详细的 LLM 调用信息。
    默认绑定到当前请求的 trace/span（由 use_langfuse_request_context 设置）。

    Returns:
        CallbackHandler 实例，如果未启用则返回 None
    """
    if not LANGFUSE_ENABLED:
        return None
    
    # 确保凭证存在
    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        return None

    effective_client = stateful_client if stateful_client is not None else _stateful_client_var.get()
    effective_user_id = user_id if user_id is not None else _user_id_var.get()
    effective_session_id = session_id if session_id is not None else _session_id_var.get()

    return CallbackHandler(
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
        host=LANGFUSE_HOST,
        stateful_client=effective_client,
        update_stateful_client=False,
        user_id=effective_user_id,
        session_id=effective_session_id,
    )


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

    # If the request already established a root trace/span, avoid creating a
    # disconnected trace via the decorator. Prefer manual spans + CallbackHandler
    # bound to the existing stateful client.
    if _stateful_client_var.get() is not None:
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    # 使用 Langfuse 的 observe 装饰器（仅用于“没有外部根 trace”的调用场景）
    return observe(
        name=name,
        capture_input=capture_input,
        capture_output=capture_output,
    )


import asyncio

async def flush_langfuse():
    """刷新 Langfuse 缓冲区，确保所有数据都发送到服务器
    
    建议在应用关闭时调用
    """
    client = _get_langfuse_client()
    if client:
        # Langfuse sync client flush is blocking, run in executor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, client.flush)


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
    "StatefulClient",
    "get_current_langfuse_stateful_client",
    "use_langfuse_request_context",
    "use_langfuse_stateful_client",
    "langfuse_observe",
    "flush_langfuse",
    "create_langfuse_session",
    "get_langfuse_callback",
]
