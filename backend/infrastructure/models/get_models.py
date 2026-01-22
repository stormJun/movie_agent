from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.callbacks.streaming_aiter import AsyncIteratorCallbackHandler
from langchain.callbacks.manager import AsyncCallbackManager
from typing import Literal

import os

from infrastructure.config.settings import (
    TIKTOKEN_CACHE_DIR,
    OPENAI_EMBEDDING_CONFIG,
    OPENAI_LLM_CONFIG,
    GEMINI_AUTH_TYPE,
    GEMINI_API_KEY,
    GEMINI_PROJECT_ID,
    GEMINI_LOCATION,
    GEMINI_LLM_MODEL,
    GEMINI_EMBEDDINGS_MODEL,
    GEMINI_TEMPERATURE,
    GEMINI_MAX_TOKENS,
    MODEL_TYPE,
)


# 设置 tiktoken 缓存目录，避免每次联网拉取
def setup_cache():
    TIKTOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["TIKTOKEN_CACHE_DIR"] = str(TIKTOKEN_CACHE_DIR)


setup_cache()


def _get_gemini_llm_model():
    """获取 Gemini LLM 模型（支持 API Key 和 OAuth 两种认证方式）"""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        raise ImportError(
            "使用 Gemini 模型需要安装 langchain-google-genai。"
            "请运行: pip install langchain-google-genai"
        )

    config = {
        "model": GEMINI_LLM_MODEL,
        "temperature": GEMINI_TEMPERATURE,
        "max_tokens": GEMINI_MAX_TOKENS,
    }

    # 移除 None 值
    config = {k: v for k, v in config.items() if v is not None}

    if GEMINI_AUTH_TYPE == "oauth":
        # OAuth 模式：使用 Google 账号认证（需要配置 ADC）
        if not GEMINI_PROJECT_ID:
            raise ValueError("OAuth 模式需要设置 GEMINI_PROJECT_ID 环境变量")
        # VertexAI 模式会自动使用 Application Default Credentials
        try:
            from langchain_google_vertexai import ChatVertexAI
            config["project"] = GEMINI_PROJECT_ID
            config["location"] = GEMINI_LOCATION
            return ChatVertexAI(**config)
        except ImportError:
            raise ImportError(
                "使用 Gemini OAuth 模式需要安装 langchain-google-vertexai。"
                "请运行: pip install langchain-google-vertexai"
            )
    else:
        # API Key 模式
        if not GEMINI_API_KEY:
            raise ValueError("API Key 模式需要设置 GEMINI_API_KEY 环境变量")
        config["api_key"] = GEMINI_API_KEY
        return ChatGoogleGenerativeAI(**config)


def _get_gemini_embeddings_model():
    """获取 Gemini 嵌入模型（支持 API Key 和 OAuth 两种认证方式）"""
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except ImportError:
        raise ImportError(
            "使用 Gemini 嵌入模型需要安装 langchain-google-genai。"
            "请运行: pip install langchain-google-genai"
        )

    config = {"model": GEMINI_EMBEDDINGS_MODEL}

    if GEMINI_AUTH_TYPE == "oauth":
        # OAuth 模式：使用 Google 账号认证
        if not GEMINI_PROJECT_ID:
            raise ValueError("OAuth 模式需要设置 GEMINI_PROJECT_ID 环境变量")
        try:
            from langchain_google_vertexai import VertexAIEmbeddings
            config["project"] = GEMINI_PROJECT_ID
            config["location"] = GEMINI_LOCATION
            return VertexAIEmbeddings(**config)
        except ImportError:
            raise ImportError(
                "使用 Gemini OAuth 模式需要安装 langchain-google-vertexai。"
                "请运行: pip install langchain-google-vertexai"
            )
    else:
        # API Key 模式
        if not GEMINI_API_KEY:
            raise ValueError("API Key 模式需要设置 GEMINI_API_KEY 环境变量")
        config["google_api_key"] = GEMINI_API_KEY
        return GoogleGenerativeAIEmbeddings(**config)


def get_embeddings_model(model_type: Literal["openai", "gemini"] | None = None):
    """获取嵌入模型，支持 OpenAI 和 Gemini

    Args:
        model_type: 模型类型，"openai" 或 "gemini"。为 None 时使用环境变量 MODEL_TYPE

    Returns:
        嵌入模型实例
    """
    if model_type is None:
        model_type = MODEL_TYPE

    if model_type == "gemini":
        return _get_gemini_embeddings_model()

    # 默认使用 OpenAI
    config = {k: v for k, v in OPENAI_EMBEDDING_CONFIG.items() if v}
    base_url = (config.get("base_url") or "").strip()
    # DashScope OpenAI 兼容模式目前不接受"token id 数组"作为 embeddings input。
    # langchain_openai 在默认 check_embedding_ctx_length=True 时会先 tiktoken 分词并传 token ids，
    # 会触发 DashScope 400 InvalidParameter（input.contents）。
    if "dashscope.aliyuncs.com/compatible-mode" in base_url:
        config["check_embedding_ctx_length"] = False
    return OpenAIEmbeddings(**config)


def get_llm_model(model_type: Literal["openai", "gemini"] | None = None):
    """获取 LLM 模型，支持 OpenAI 和 Gemini

    Args:
        model_type: 模型类型，"openai" 或 "gemini"。为 None 时使用环境变量 MODEL_TYPE

    Returns:
        LLM 模型实例
    """
    if model_type is None:
        model_type = MODEL_TYPE

    if model_type == "gemini":
        return _get_gemini_llm_model()

    # 默认使用 OpenAI
    config = {k: v for k, v in OPENAI_LLM_CONFIG.items() if v is not None and v != ""}
    return ChatOpenAI(**config)


def get_stream_llm_model(model_type: Literal["openai", "gemini"] | None = None):
    """获取流式 LLM 模型，支持 OpenAI 和 Gemini

    Args:
        model_type: 模型类型，"openai" 或 "gemini"。为 None 时使用环境变量 MODEL_TYPE

    Returns:
        流式 LLM 模型实例
    """
    if model_type is None:
        model_type = MODEL_TYPE

    if model_type == "gemini":
        # Gemini 原生支持流式，不需要额外的 callback handler
        return _get_gemini_llm_model()

    # OpenAI 需要配置流式处理
    callback_handler = AsyncIteratorCallbackHandler()
    # 将回调handler放进AsyncCallbackManager中
    manager = AsyncCallbackManager(handlers=[callback_handler])

    config = {k: v for k, v in OPENAI_LLM_CONFIG.items() if v is not None and v != ""}
    config.update({"streaming": True, "callbacks": manager})
    return ChatOpenAI(**config)

def count_tokens(text):
    """简单通用的token计数"""
    if not text:
        return 0
    
    model_name = (OPENAI_LLM_CONFIG.get("model") or "").lower()
    
    # 如果是deepseek，使用transformers
    if 'deepseek' in model_name:
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained("deepseek-ai/DeepSeek-V3")
            return len(tokenizer.encode(text))
        except:
            pass
    
    # 如果是gpt，使用tiktoken
    if 'gpt' in model_name:
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except:
            pass
    
    # 备用方案：简单计算
    chinese = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
    english = len(text) - chinese
    return chinese + english // 4

if __name__ == '__main__':
    # 测试llm
    llm = get_llm_model()
    print(llm.invoke("你好"))

    # 由于langchain版本问题，这个目前测试会报错
    # llm_stream = get_stream_llm_model()
    # print(llm_stream.invoke("你好"))

    # 测试embedding
    test_text = "你好，这是一个测试。"
    embeddings = get_embeddings_model()
    print(embeddings.embed_query(test_text))

    # 测试计数
    test_text = "Hello 你好世界"
    tokens = count_tokens(test_text)
    print(f"Token计数: '{test_text}' = {tokens} tokens")
