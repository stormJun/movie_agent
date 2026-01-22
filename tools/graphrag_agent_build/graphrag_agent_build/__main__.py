from __future__ import annotations

from graphrag_agent_build.main import KnowledgeGraphProcessor


def main() -> None:
    processor = KnowledgeGraphProcessor()
    processor.process_all()


if __name__ == "__main__":
    main()

