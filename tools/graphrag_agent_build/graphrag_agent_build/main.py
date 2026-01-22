import os

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from infrastructure.graph import connection_manager
from graphrag_agent_build.build_graph import KnowledgeGraphBuilder
from graphrag_agent_build.build_index_and_community import IndexCommunityBuilder
from graphrag_agent_build.build_chunk_index import ChunkIndexBuilder
from graphrag_agent_build.structured_movie_graph import StructuredMovieGraphBuilder
from graphrag_agent.config.settings import (
    DOCUMENT_KB_PREFIX,
    ENTITY_VECTOR_INDEX_NAME,
    GRAPH_BUILD_MODE,
)

class KnowledgeGraphProcessor:
    """
    知识图谱处理器，整合了图谱构建和索引处理的完整流程。
    可以选择完整流程或单独执行其中一个步骤。
    """

    def __init__(self):
        """初始化知识图谱处理器"""
        self.console = Console()

    @staticmethod
    def _get_env_bool(key: str, default: bool) -> bool:
        raw = os.getenv(key)
        if raw is None or raw.strip() == "":
            return default
        return raw.strip().lower() in {"1", "true", "yes", "y", "on"}

    def process_all(self):
        """执行完整的处理流程"""
        try:
            # 显示开始面板
            start_text = Text("开始知识图谱处理流程", style="bold cyan")
            self.console.print(Panel(start_text, border_style="cyan"))

            mode = GRAPH_BUILD_MODE

            # 0. 清除旧索引（默认仅 document 模式执行，structured 模式建议使用独立索引名避免影响其他知识库）
            # 同库多 KB 共存时（document + DOCUMENT_KB_PREFIX 非空），默认禁止全库删索引。
            drop_all_indexes_default = True if mode == "document" and not DOCUMENT_KB_PREFIX else False
            drop_all_indexes = self._get_env_bool("BUILD_DROP_ALL_INDEXES", drop_all_indexes_default)

            if drop_all_indexes:
                self.console.print("\n[bold yellow]步骤 0: 清除所有旧索引[/bold yellow]")
                connection_manager.drop_all_indexes()
            else:
                self.console.print("\n[bold yellow]步骤 0: 跳过清除所有旧索引[/bold yellow]")
                if mode == "structured" and ENTITY_VECTOR_INDEX_NAME == "vector":
                    self.console.print(
                        "[yellow]提示: 当前实体向量索引名为 'vector'，若与其他知识库共库，建议设置 "
                        "LOCAL_SEARCH_INDEX_NAME=movie_vector 或 ENTITY_VECTOR_INDEX_NAME=movie_vector 以隔离索引。[/yellow]"
                    )

            # 1. 构建基础图谱
            run_graph = self._get_env_bool("BUILD_RUN_GRAPH", True)
            if run_graph:
                self.console.print("\n[bold cyan]步骤 1: 构建基础图谱[/bold cyan]")
                if mode == "document":
                    graph_builder = KnowledgeGraphBuilder()
                    graph_builder.process()
                else:
                    structured_builder = StructuredMovieGraphBuilder(
                        reset_domain_graph=self._get_env_bool("STRUCTURED_RESET_DOMAIN", False),
                        reset_canonical_layer=self._get_env_bool("STRUCTURED_RESET_CANONICAL", False),
                        kb_prefix=os.getenv("STRUCTURED_KB_PREFIX", "movie"),
                        batch_size=int(os.getenv("STRUCTURED_BATCH_SIZE", "500")),
                    )
                    structured_builder.process()
            else:
                self.console.print("\n[bold cyan]步骤 1: 跳过基础图谱构建[/bold cyan]")

            # 2. 构建实体索引和社区
            run_index = self._get_env_bool("BUILD_RUN_INDEX_AND_COMMUNITY", True)
            if run_index:
                self.console.print("\n[bold cyan]步骤 2: 构建实体索引和社区[/bold cyan]")
                index_builder = IndexCommunityBuilder()
                index_builder.process()
            else:
                self.console.print("\n[bold cyan]步骤 2: 跳过实体索引和社区[/bold cyan]")

            # 3. 构建Chunk索引
            run_chunk = self._get_env_bool("BUILD_RUN_CHUNK_INDEX", True)
            if run_chunk:
                self.console.print("\n[bold cyan]步骤 3: 构建Chunk索引[/bold cyan]")
                chunk_index_builder = ChunkIndexBuilder()
                chunk_index_builder.process()
            else:
                self.console.print("\n[bold cyan]步骤 3: 跳过Chunk索引[/bold cyan]")

            # 显示完成面板
            success_text = Text("知识图谱处理流程完成", style="bold green")
            self.console.print(Panel(success_text, border_style="green"))

        except Exception as e:
            error_text = Text(f"处理过程中出现错误: {str(e)}", style="bold red")
            self.console.print(Panel(error_text, border_style="red"))
            raise

if __name__ == "__main__":
    try:
        from infrastructure.bootstrap import bootstrap_core_ports

        bootstrap_core_ports()
        processor = KnowledgeGraphProcessor()
        processor.process_all()
    except Exception as e:
        console = Console()
        console.print(f"[red]执行过程中出现错误: {str(e)}[/red]")
