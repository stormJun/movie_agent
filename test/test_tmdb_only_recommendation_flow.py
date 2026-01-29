import unittest
from unittest.mock import patch

from domain.chat.entities.route_decision import RouteDecision
from infrastructure.rag.retrieval_subgraph import retrieval_subgraph_compiled
from langgraph.constants import CONFIG_KEY_STREAM_WRITER


class _FakeTmdbStore:
    def __init__(self) -> None:
        self.jobs = []

    async def persist_enrichment(self, **job):  # type: ignore[no-untyped-def]
        self.jobs.append(job)


class _FakeTmdbClient:
    async def resolve_entity_via_multi(self, *, text: str, query: str):  # type: ignore[no-untyped-def]
        # No seed in this test.
        return None, {"type": "multi", "entity": text, "query_text": query}

    async def movie_recommendations_raw(self, *, movie_id: int, language: str, page: int):  # type: ignore[no-untyped-def]
        return {"results": []}

    async def discover_movie_raw(self, *, language: str, page: int, sort_by: str, filters=None):  # type: ignore[no-untyped-def]
        _ = (language, page, sort_by, filters)
        return {"results": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}, {"id": 6}]}

    async def get_movie_details(self, movie_id: int, *, language: str):  # type: ignore[no-untyped-def]
        _ = language
        return {
            "id": int(movie_id),
            "title": f"Movie {movie_id}",
            "overview": f"Overview {movie_id}",
            "release_date": "2024-01-01",
            "vote_average": 8.0,
            "genres": [{"id": 18, "name": "Drama"}],
            "credits": {"cast": [], "crew": [{"job": "Director", "name": "Someone"}]},
        }


class _FakeTmdbService:
    def __init__(self) -> None:
        self._store = _FakeTmdbStore()
        self._client = _FakeTmdbClient()

    def get_store(self):
        return self._store

    def get_client(self):
        return self._client


class TestTmdbOnlyRecommendationFlow(unittest.IsolatedAsyncioTestCase):
    async def test_tmdb_only_recommendation_emits_ids_and_prebuilt_answer(self) -> None:
        events = []

        def writer(ev):
            events.append(ev)

        async def _bad_retrieval_runner(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise AssertionError("GraphRAG retrieval should not run in TMDB-only recommend flow")

        route = RouteDecision(
            requested_kb_prefix="movie",
            routed_kb_prefix="movie",
            kb_prefix="movie",
            confidence=0.99,
            method="stub",
            reason="test",
            worker_name="movie:fusion_agent:retrieve_only",
            query_intent="recommend",
            media_type_hint="movie",
            extracted_entities={"low_level": [], "high_level": ["电影"]},
        )

        fake_service = _FakeTmdbService()

        async def _fake_select(*, question: str, candidates, k: int = 5):  # type: ignore[no-untyped-def]
            _ = (question, candidates, k)
            return [
                {"tmdb_id": 1, "title": "Movie 1", "year": 2024, "blurb": "B1"},
                {"tmdb_id": 2, "title": "Movie 2", "year": 2024, "blurb": "B2"},
                {"tmdb_id": 3, "title": "Movie 3", "year": 2024, "blurb": "B3"},
                {"tmdb_id": 4, "title": "Movie 4", "year": 2024, "blurb": "B4"},
                {"tmdb_id": 5, "title": "Movie 5", "year": 2024, "blurb": "B5"},
            ]

        with patch("infrastructure.enrichment.get_tmdb_enrichment_service", return_value=fake_service):
            with patch(
                "infrastructure.rag.retrieval_subgraph.select_tmdb_recommendation_movies",
                side_effect=_fake_select,
            ):
                out = await retrieval_subgraph_compiled.ainvoke(
                    {
                        "query": "推荐几个电影",
                        "kb_prefix": "movie",
                        "route_decision": route,
                        "debug": False,
                        "session_id": "s1",
                        "user_id": "u1",
                        "request_id": "r1",
                        "conversation_id": "c1",
                        "user_message_id": "m1",
                        "incognito": False,
                        "resolved_agent_type": "fusion_agent",
                        "tmdb_only_recommendation": True,
                    },
                    config={
                        "configurable": {
                            "retrieval_runner": _bad_retrieval_runner,
                            CONFIG_KEY_STREAM_WRITER: writer,
                        }
                    },
                )

        # Ensure a recommendations event is emitted with the selected ids.
        reco = [e for e in events if isinstance(e, dict) and e.get("status") == "recommendations"]
        self.assertTrue(reco)
        ids = reco[-1]["content"]["tmdb_ids"]
        self.assertEqual(ids, [1, 2, 3, 4, 5])

        merged = out.get("merged")
        self.assertTrue(merged is not None)
        stats = getattr(merged, "statistics", None)
        self.assertTrue(isinstance(stats, dict) and stats.get("tmdb_only_recommendation"))
        answer = stats.get("answer")
        self.assertTrue(isinstance(answer, str) and "《Movie 1》" in answer and "《Movie 5》" in answer)
