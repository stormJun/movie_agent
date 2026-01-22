"""
Neo4j 工具函数模块

提供通用的 Neo4j 查询辅助功能，包括：
- 参数内联到 Cypher 查询
- 查询结果格式化
- 查询性能统计
- 连接健康检查
"""

from typing import Any, Dict, List
from collections import defaultdict
from datetime import datetime
import logging
import time

from neo4j import Driver

logger = logging.getLogger(__name__)

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore


class Neo4jQueryStats:
    """查询性能统计器"""

    def __init__(self):
        self.query_counts: Dict[str, int] = defaultdict(int)
        self.query_times: Dict[str, List[float]] = defaultdict(list)
        self.slow_queries: List[Dict[str, Any]] = []
        self.slow_threshold: float = 1.0  # 秒

    def record_query(self, query_signature: str, elapsed: float, cypher: str = ""):
        """记录查询性能"""
        self.query_counts[query_signature] += 1
        self.query_times[query_signature].append(elapsed)

        # 记录慢查询
        if elapsed > self.slow_threshold:
            self.slow_queries.append({
                "signature": query_signature,
                "elapsed": elapsed,
                "cypher_preview": cypher[:200] if cypher else "",
                "timestamp": datetime.now().isoformat()
            })

    def get_stats_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        summary = {
            "total_queries": sum(self.query_counts.values()),
            "unique_queries": len(self.query_counts),
            "slow_queries_count": len(self.slow_queries),
        }

        # 计算平均执行时间
        avg_times = {}
        for sig, times in self.query_times.items():
            avg_times[sig] = sum(times) / len(times)

        summary["avg_times"] = dict(sorted(
            avg_times.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10])  # Top 10 最慢查询（平均）

        return summary

    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取慢查询列表"""
        return sorted(
            self.slow_queries,
            key=lambda x: x["elapsed"],
            reverse=True
        )[:limit]


# 全局统计实例
_query_stats = Neo4jQueryStats()


def get_query_stats() -> Neo4jQueryStats:
    """获取全局查询统计器实例"""
    return _query_stats


class Neo4jQueryHelper:
    """Neo4j 查询辅助工具类"""

    @staticmethod
    def inline_params(cypher: str, params: Dict[str, Any]) -> str:
        """
        将参数内联到 Cypher 查询中，生成可直接执行的查询语句

        支持的数据类型：
        - 字符串: 自动转义单引号，用单引号包裹
        - 列表/元组: 转换为 Cypher 数组格式 ['item1', 'item2']
        - 布尔值: 转为 Cypher 关键字 true/false
        - 数字: 直接转换
        - null: 转为 Cypher 的 null

        参数:
            cypher: Cypher 查询模板
            params: 参数字典

        返回:
            str: 参数已内联的 Cypher 查询
        """
        if not params:
            return cypher

        inlined = cypher
        # 按参数名长度降序排序，避免短名称被长名称的子串替换
        for param_name in sorted(params.keys(), key=len, reverse=True):
            param_value = params[param_name]
            placeholder = f"${param_name}"

            try:
                formatted = Neo4jQueryHelper._format_value(param_value)
                # 替换所有出现的占位符
                inlined = inlined.replace(placeholder, formatted)
            except Exception as e:
                logger.warning(
                    "Failed to format parameter '%s': %s",
                    param_name,
                    e,
                    exc_info=True,
                )
                # 格式化失败时保留占位符
                continue

        return inlined

    @staticmethod
    def _format_value(value: Any) -> str:
        """格式化单个参数值为 Cypher 字面量"""
        if isinstance(value, str):
            # 字符串：转义单引号，用单引号包裹
            escaped = value.replace("'", "\\'")
            return f"'{escaped}'"

        elif isinstance(value, (list, tuple)):
            # 列表：转换为 ['item1', 'item2'] 格式
            items = []
            for item in value:
                if isinstance(item, str):
                    escaped = item.replace("'", "\\'")
                    items.append(f"'{escaped}'")
                elif isinstance(item, bool):
                    items.append("true" if item else "false")
                elif item is None:
                    items.append("null")
                elif isinstance(item, (int, float)):
                    items.append(str(item))
                else:
                    # 嵌套列表中的其他类型转为字符串
                    escaped = str(item).replace("'", "\\'")
                    items.append(f"'{escaped}'")
            return f"[{', '.join(items)}]"

        elif isinstance(value, bool):
            # 布尔值：转为 Cypher 关键字 true/false
            return "true" if value else "false"

        elif value is None:
            # null 值
            return "null"

        elif isinstance(value, (int, float)):
            # 数字：直接转换
            return str(value)

        else:
            # 其他类型：转为字符串并转义
            escaped = str(value).replace("'", "\\'")
            return f"'{escaped}'"

    @staticmethod
    def format_result_preview(result: Any, max_rows: int = 3, max_col_width: int = 50) -> str:
        """
        格式化 Neo4j 查询结果为可读的预览字符串

        支持多种结果格式：
        - pandas.DataFrame: 表格格式，截断长内容
        - list: 列表格式，显示前几个元素
        - other: 转为字符串并截断

        参数:
            result: Neo4j 查询结果（DataFrame、列表等）
            max_rows: 最多显示的行数（默认3行）
            max_col_width: 每列最大字符宽度（默认50）

        返回:
            str: 格式化后的预览字符串
        """
        # 处理 None
        if result is None:
            return "Empty result"

        # 处理 pandas.DataFrame（pandas 为可选依赖）
        if pd is not None and isinstance(result, pd.DataFrame):
            if len(result) == 0:
                return "Empty DataFrame"

            # 截取前 max_rows 行
            preview_df = result.head(max_rows)

            # 截断每列的内容
            truncated_df = preview_df.copy()
            for col in truncated_df.columns:
                truncated_df[col] = truncated_df[col].apply(
                    lambda x: str(x)[:max_col_width] + "..." if len(str(x)) > max_col_width else str(x)
                )

            # 转换为字符串
            formatted = truncated_df.to_string(index=False)

            # 如果有更多行，添加省略标记
            if len(result) > max_rows:
                formatted += f"\n... ({len(result) - max_rows} more rows)"

            return formatted

        # 处理列表
        if isinstance(result, list):
            if len(result) == 0:
                return "Empty list"

            first_item = str(result[0])[:50]
            return f"List with {len(result)} items (first: {first_item}...)"

        # 处理字典
        if isinstance(result, dict):
            preview = str(result)
            if len(preview) > 200:
                preview = preview[:200] + "..."
            return f"Dict: {preview}"

        # 其他类型：转为字符串并截断
        result_str = str(result)
        if len(result_str) > 200:
            result_str = result_str[:200] + "..."
        return result_str

    @staticmethod
    def log_query(cypher: str, params: Dict[str, Any], logger_instance: logging.Logger = None) -> None:
        """
        记录 Neo4j 查询日志（参数已内联）

        参数:
            cypher: Cypher 查询语句
            params: 查询参数
            logger_instance: 日志记录器实例，如果为 None 则使用模块默认 logger
        """
        log = logger_instance or logger

        try:
            inlined_cypher = Neo4jQueryHelper.inline_params(cypher, params)
            log.info("[neo4j.db_query] %s", inlined_cypher)
        except Exception as e:
            # 回退到原始日志方式
            log.warning(
                "Failed to inline query parameters: %s. Falling back to separate logging.",
                e
            )
            log.info("[neo4j.db_query] cypher:\n%s", cypher)
            log.info("[neo4j.db_query] params=%s", params)

    @staticmethod
    def log_query_with_result(
        cypher: str,
        params: Dict[str, Any],
        result: Any,
        elapsed_seconds: float,
        logger_instance: logging.Logger = None
    ) -> None:
        """
        记录 Neo4j 查询及其结果的完整日志

        参数:
            cypher: Cypher 查询语句
            params: 查询参数
            result: 查询结果
            elapsed_seconds: 执行耗时（秒）
            logger_instance: 日志记录器实例，如果为 None 则使用模块默认 logger
        """
        log = logger_instance or logger

        # 计算结果行数
        if isinstance(result, pd.DataFrame):
            row_count = len(result)
        elif isinstance(result, list):
            row_count = len(result)
        else:
            row_count = 0

        # INFO 级别：基本信息
        log.info(
            "[neo4j.db_query] done: rows=%d elapsed_seconds=%.4f",
            row_count,
            elapsed_seconds,
        )

        # DEBUG 级别：结果预览
        if row_count > 0:
            preview = Neo4jQueryHelper.format_result_preview(result, max_rows=3, max_col_width=60)
            log.debug("[neo4j.db_query] result_preview:\n%s", preview)

        # 记录到性能统计器
        query_sig = Neo4jQueryHelper._generate_query_signature(cypher)
        _query_stats.record_query(query_sig, elapsed_seconds, cypher)

        # 慢查询警告
        if elapsed_seconds > _query_stats.slow_threshold:
            log.warning(
                "[neo4j.db_query] SLOW QUERY (%.2fs): %s",
                elapsed_seconds,
                query_sig
            )

    @staticmethod
    def _generate_query_signature(cypher: str) -> str:
        """
        生成查询签名（用于统计）

        参数:
            cypher: Cypher 查询语句

        返回:
            str: 查询签名（去除参数和空格的标准化形式）
        """
        # 移除注释和多余空格，提取主要关键词
        cleaned = ' '.join(cypher.split())
        # 截取前 100 个字符作为签名
        return cleaned[:100] if len(cleaned) > 100 else cleaned

    @staticmethod
    def check_connection(driver: Driver) -> Dict[str, Any]:
        """
        检查 Neo4j 连接健康状态

        参数:
            driver: Neo4j Driver 实例

        返回:
            Dict: 包含连接状态、版本、响应时间等信息
        """
        health_info = {
            "healthy": False,
            "version": None,
            "response_time_ms": None,
            "error": None
        }

        try:
            start = time.time()
            with driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            elapsed_ms = (time.time() - start) * 1000

            # 获取 Neo4j 版本
            with driver.session() as session:
                result = session.run("RETURN neo4j.version() AS version")
                record = result.single()
                version = record["version"] if record else None

            health_info.update({
                "healthy": True,
                "version": version,
                "response_time_ms": round(elapsed_ms, 2),
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            health_info["error"] = str(e)
            logger.error("Neo4j connection check failed: %s", e)

        return health_info


# ========== 便捷函数接口 ==========

def inline_cypher_params(cypher: str, params: Dict[str, Any]) -> str:
    """将参数内联到 Cypher 查询中的便捷函数"""
    return Neo4jQueryHelper.inline_params(cypher, params)


def format_neo4j_result(result: Any, max_rows: int = 3, max_col_width: int = 50) -> str:
    """格式化 Neo4j 查询结果的便捷函数"""
    return Neo4jQueryHelper.format_result_preview(result, max_rows, max_col_width)


def log_neo4j_query(cypher: str, params: Dict[str, Any], logger_instance: logging.Logger = None) -> None:
    """记录 Neo4j 查询日志的便捷函数"""
    Neo4jQueryHelper.log_query(cypher, params, logger_instance)


def log_neo4j_query_with_result(
    cypher: str,
    params: Dict[str, Any],
    result: Any,
    elapsed_seconds: float,
    logger_instance: logging.Logger = None
) -> None:
    """记录 Neo4j 查询及其结果的便捷函数"""
    Neo4jQueryHelper.log_query_with_result(cypher, params, result, elapsed_seconds, logger_instance)


def check_neo4j_connection(driver: Driver) -> Dict[str, Any]:
    """检查 Neo4j 连接健康状态的便捷函数"""
    return Neo4jQueryHelper.check_connection(driver)


def get_query_stats_summary() -> Dict[str, Any]:
    """获取查询统计摘要"""
    return _query_stats.get_stats_summary()


def get_slow_queries(limit: int = 10) -> List[Dict[str, Any]]:
    """获取慢查询列表"""
    return _query_stats.get_slow_queries(limit)


def set_slow_query_threshold(seconds: float) -> None:
    """设置慢查询阈值"""
    _query_stats.slow_threshold = seconds
    logger.info("Slow query threshold set to %.2f seconds", seconds)
