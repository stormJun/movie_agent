#!/usr/bin/env python3
"""
Run the full GraphRAG build pipeline (step0~step3) asynchronously with progress.

This script is designed to be launched via nohup/background. It writes a JSON
status file that can be polled to check progress.
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from infrastructure.bootstrap import bootstrap_core_ports

bootstrap_core_ports()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _collect_metrics() -> dict[str, int]:
    from graphrag_agent.ports.neo4jdb import get_graph

    graph = get_graph()

    def _count(query: str) -> int:
        rows = graph.query(query)
        return int(rows[0]["c"]) if rows else 0

    return {
        "documents": _count("MATCH (d:`__Document__`) RETURN count(d) AS c"),
        "chunks": _count("MATCH (c:`__Chunk__`) RETURN count(c) AS c"),
        "entities": _count("MATCH (e:`__Entity__`) RETURN count(e) AS c"),
        "mentions": _count("MATCH ()-[r:MENTIONS]->() RETURN count(r) AS c"),
        "chunks_with_embedding": _count(
            "MATCH (c:`__Chunk__`) WHERE c.embedding IS NOT NULL RETURN count(c) AS c"
        ),
    }


@dataclass
class BuildStatus:
    path: Path
    payload: dict[str, Any]

    def update(self, **kwargs: Any) -> None:
        self.payload.update(kwargs)
        _write_json(self.path, self.payload)

    def update_stage(self, stage: str) -> None:
        # Reset per-stage completion marker when entering a new stage.
        self.payload.pop("stage_completed_at", None)
        self.update(stage=stage, stage_started_at=_now_iso())

    def mark_failed(self, error: str) -> None:
        self.update(stage="failed", failed_at=_now_iso(), error=error)

    def mark_completed(self) -> None:
        self.update(stage="completed", completed_at=_now_iso())


def _heartbeat_loop(status: BuildStatus, stop: Event, interval_seconds: int) -> None:
    while not stop.is_set():
        try:
            status.update(
                last_heartbeat_at=_now_iso(),
                metrics=_collect_metrics(),
            )
        except Exception as exc:
            status.update(last_heartbeat_at=_now_iso(), heartbeat_error=str(exc))
        stop.wait(interval_seconds)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status-path",
        default="logs/full_build_status.json",
        help="Where to write JSON status for progress polling.",
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=30,
        help="How often to refresh metrics in the status file.",
    )
    parser.add_argument(
        "--text-chunker-provider",
        default=os.getenv("TEXT_CHUNKER_PROVIDER", "simple"),
        help="Override TEXT_CHUNKER_PROVIDER (default: simple to avoid HanLP instability).",
    )
    args = parser.parse_args(argv)

    # Ensure env is set BEFORE importing graphrag_agent modules (settings reads env at import time).
    os.environ.setdefault("GRAPH_BUILD_MODE", "full")
    os.environ["TEXT_CHUNKER_PROVIDER"] = str(args.text_chunker_provider)
    faulthandler.enable(all_threads=True)
    try:
        faulthandler.register(signal.SIGUSR1, all_threads=True)
    except Exception:
        # Not all platforms allow registering SIGUSR1; ignore.
        pass

    status_path = Path(args.status_path)
    status = BuildStatus(
        path=status_path,
        payload={
            "pid": os.getpid(),
            "started_at": _now_iso(),
            "stage": "starting",
            "text_chunker_provider": os.environ.get("TEXT_CHUNKER_PROVIDER"),
            "graph_build_mode": os.environ.get("GRAPH_BUILD_MODE"),
        },
    )
    status.update(metrics=_collect_metrics())

    stop = Event()
    heartbeat = Thread(
        target=_heartbeat_loop,
        args=(status, stop, int(args.heartbeat_seconds)),
        daemon=True,
    )
    heartbeat.start()

    try:
        status.update_stage("step0_drop_indexes")
        from infrastructure.graph import connection_manager

        connection_manager.drop_all_indexes()
        status.update(metrics=_collect_metrics(), stage_completed_at=_now_iso())

        status.update_stage("step1_build_graph")
        from infrastructure.integrations.build.build_graph import KnowledgeGraphBuilder

        KnowledgeGraphBuilder(extract_entities=True).process()
        status.update(metrics=_collect_metrics(), stage_completed_at=_now_iso())

        status.update_stage("step2_index_community")
        from infrastructure.integrations.build.build_index_and_community import (
            IndexCommunityBuilder,
        )

        IndexCommunityBuilder().process()
        status.update(metrics=_collect_metrics(), stage_completed_at=_now_iso())

        status.update_stage("step3_chunk_index")
        from infrastructure.integrations.build.build_chunk_index import ChunkIndexBuilder

        ChunkIndexBuilder().process()
        status.update(metrics=_collect_metrics(), stage_completed_at=_now_iso())

        status.mark_completed()
        return 0
    except Exception as exc:
        status.mark_failed(str(exc))
        raise
    finally:
        stop.set()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
