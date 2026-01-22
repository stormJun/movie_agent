from typing import Any, Dict, List, Optional

from langchain_core.tools import BaseTool

from graphrag_agent.search.tool.reasoning.validator import AnswerValidator
from graphrag_agent.search.tool.hybrid_tool import HybridSearchTool


class AnswerValidationTool:
    """
    将AnswerValidator封装成LangChain Tool。
    默认复用HybridSearchTool的关键词提取能力以评估相关性。
    """

    def __init__(self):
        keyword_tool = HybridSearchTool()
        self.validator = AnswerValidator(keyword_tool.extract_keywords)

    def validate(
        self,
        query: str,
        answer: str,
        *,
        reference_keywords: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        if not query:
            raise ValueError("query不能为空")
        if answer is None:
            answer = ""
        result = self.validator.validate(
            query,
            answer,
            reference_keywords=reference_keywords,
        )
        return {"query": query, "answer": answer, "validation": result}

    def retrieve_only(self, query_input: Any) -> Dict[str, Any]:
        """
        非检索型工具的“retrieve_only”兼容接口：
        仅做答案质量评估，不调用检索链路，也不生成最终答案。
        """
        payload = query_input
        query = ""
        answer = ""
        reference_keywords: Optional[Dict[str, List[str]]] = None

        if isinstance(payload, dict):
            query = str(payload.get("query") or payload.get("input") or "").strip()
            answer = str(payload.get("answer") or "").strip()
            reference_keywords = payload.get("reference_keywords")
        else:
            query = str(payload or "").strip()

        if not query:
            raise ValueError("query不能为空")

        result = self.validate(query, answer, reference_keywords=reference_keywords)
        validation = result.get("validation") if isinstance(result, dict) else None
        return {
            "query": query,
            "answer": answer,
            "validation": validation if isinstance(validation, dict) else {},
            "context": str(validation) if validation is not None else "",
            "retrieval_results": [],
        }

    def get_tool(self) -> BaseTool:
        validator = self

        class AnswerValidatorLC(BaseTool):
            name: str = "answer_validator"
            description: str = "答案质量验证工具：基于关键词与错误模式检测评估回答的长度、相关性与可用性。"

            def _run(
                self_tool,
                query: Any,
                answer: str = "",
                reference_keywords: Optional[Dict[str, List[str]]] = None,
                **kwargs: Any,
            ) -> Dict[str, Any]:
                payload_query = query
                payload_answer = answer
                if isinstance(query, dict):
                    payload_query = query.get("query") or query.get("input") or ""
                    payload_answer = query.get("answer") or answer
                    reference_keywords = query.get("reference_keywords") or reference_keywords
                return validator.validate(
                    str(payload_query),
                    str(payload_answer),
                    reference_keywords=reference_keywords,
                )

            def _arun(self_tool, *args: Any, **kwargs: Any) -> Any:
                raise NotImplementedError("异步执行未实现")

        return AnswerValidatorLC()
