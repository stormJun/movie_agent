from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from config.rag import community_algorithm


class ChatRequest(BaseModel):
    """聊天请求模型"""
    user_id: str
    message: str
    session_id: str
    kb_prefix: Optional[str] = None
    debug: bool = False
    # User-controlled privacy mode: do not read/write memory-related contexts,
    # and skip all post-turn memory side effects (summary/episodic/mem0/watchlist).
    incognito: Optional[bool] = False
    # Per-request override for watchlist auto-capture. Global server config still applies.
    watchlist_auto_capture: Optional[bool] = None
    agent_type: str = "naive_rag_agent"
    use_deeper_tool: Optional[bool] = True
    show_thinking: Optional[bool] = False


class ChatResponse(BaseModel):
    """聊天响应模型"""
    answer: str
    debug: Optional[bool] = None
    execution_log: Optional[List[Dict]] = None
    kg_data: Optional[Dict] = None
    reference: Optional[Dict] = None
    retrieval_results: Optional[List[Dict[str, Any]]] = None
    iterations: Optional[List[Dict]] = None
    rag_runs: Optional[List[Dict[str, Any]]] = None
    route_decision: Optional[Dict[str, Any]] = None
    # Best-effort post-turn side-effects for UX (e.g., watchlist auto-capture).
    watchlist_auto_capture: Optional[Dict[str, Any]] = None


class SourceRequest(BaseModel):
    """源内容请求模型"""
    source_id: str


class SourceResponse(BaseModel):
    """源内容响应模型"""
    content: str


class SourceInfoResponse(BaseModel):
    """源文件信息响应模型"""
    file_name: str


class ClearRequest(BaseModel):
    """清除聊天历史请求模型"""
    user_id: str
    session_id: str
    kb_prefix: Optional[str] = None


class ClearResponse(BaseModel):
    """清除聊天历史响应模型"""
    status: str
    remaining_messages: Optional[str] = None


class FeedbackRequest(BaseModel):
    """反馈请求模型"""
    message_id: str
    query: str
    is_positive: bool
    thread_id: str
    # Optional Langfuse trace id (aka request_id in streaming API). When provided we
    # can attach a Langfuse score to the right trace.
    request_id: Optional[str] = None
    agent_type: Optional[str] = "naive_rag_agent"


class FeedbackResponse(BaseModel):
    """反馈响应模型"""
    status: str
    action: str
    # positive | negative | none
    feedback: Optional[str] = None

class SourceInfoBatchRequest(BaseModel):
    source_ids: List[str]

class ContentBatchRequest(BaseModel):
    chunk_ids: List[str]

class ReasoningRequest(BaseModel):
    reasoning_type: str
    entity_a: str
    entity_b: Optional[str] = None
    max_depth: Optional[int] = 3
    algorithm: Optional[str] = community_algorithm

class EntityData(BaseModel):
    id: str
    name: str
    type: str
    description: Optional[str] = ""
    properties: Optional[Dict[str, Any]] = {}

class EntityUpdateData(BaseModel):
    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None

class EntitySearchFilter(BaseModel):
    term: Optional[str] = None
    type: Optional[str] = None
    limit: Optional[int] = 100

class RelationData(BaseModel):
    source: str
    type: str
    target: str
    description: Optional[str] = ""
    weight: Optional[float] = 0.5
    properties: Optional[Dict[str, Any]] = {}

class RelationUpdateData(BaseModel):
    source: str
    original_type: str
    target: str
    new_type: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    properties: Optional[Dict[str, Any]] = None

class RelationSearchFilter(BaseModel):
    source: Optional[str] = None
    target: Optional[str] = None
    type: Optional[str] = None
    limit: Optional[int] = 100

class EntityDeleteData(BaseModel):
    id: str

class RelationDeleteData(BaseModel):
    source: str
    type: str
    target: str
