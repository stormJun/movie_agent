import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient


class _FakeTmdbStore:
    """Fake TMDB store for mp movies endpoints (no Postgres required)."""

    def __init__(self) -> None:
        self._rows = {
            1084242: {
                "tmdb_id": 1084242,
                "title": "疯狂动物城2",
                "original_title": "Zootopia 2",
                "release_date": "2025-11-26",
                "popularity": 100.0,
                "vote_average": 7.6,
                "vote_count": 100,
                "raw": {
                    "poster_path": "/p.jpg",
                    "backdrop_path": "/b.jpg",
                    "overview": "test overview",
                    "genres": [{"id": 16, "name": "动画"}],
                    "credits": {
                        "cast": [{"name": "Actor A", "character": "X"}],
                        "crew": [{"name": "Director A", "job": "Director"}],
                    },
                    "runtime": 120,
                },
            }
        }

    async def get_movies(self, *, tmdb_ids: list[int]) -> list[dict]:
        out: list[dict] = []
        for mid in tmdb_ids:
            row = self._rows.get(int(mid))
            if row:
                out.append(dict(row))
        return out

    async def get_movie(self, *, tmdb_id: int) -> dict | None:
        row = self._rows.get(int(tmdb_id))
        return dict(row) if row else None

    async def persist_enrichment(self, **_kwargs) -> None:
        # Fetch-through paths call this; we don't need it for contract tests.
        return None

    async def list_movies_feed(self, **_kwargs) -> list[dict]:
        return [dict(v) for v in self._rows.values()]


class TestMpMoviesContract(unittest.TestCase):
    def setUp(self) -> None:
        from server.main import app

        self.client = TestClient(app)

    def test_movies_bulk_returns_tmdb_id_for_clickthrough(self) -> None:
        fake = _FakeTmdbStore()
        with patch("server.api.rest.v1.mp_movies._get_tmdb_store", return_value=fake):
            r = self.client.post("/api/v1/mp/movies/bulk", json={"ids": [1084242]})
        self.assertEqual(r.status_code, 200, r.text)
        payload = r.json()
        self.assertIsInstance(payload.get("items"), list)
        self.assertEqual(payload["items"][0]["tmdb_id"], 1084242)
        # Directors/genres come from raw. If these are empty, the UI feels broken.
        self.assertTrue(payload["items"][0]["directors"])
        self.assertTrue(payload["items"][0]["genres"])

    def test_movie_detail_has_required_fields(self) -> None:
        fake = _FakeTmdbStore()
        with patch("server.api.rest.v1.mp_movies._get_tmdb_store", return_value=fake):
            r = self.client.get("/api/v1/mp/movies/1084242")
        self.assertEqual(r.status_code, 200, r.text)
        payload = r.json()
        movie = payload.get("movie") or {}
        self.assertEqual(movie.get("tmdb_id"), 1084242)
        self.assertTrue(movie.get("title"))
        self.assertTrue(movie.get("directors"))
        self.assertTrue(movie.get("genres"))


if __name__ == "__main__":
    unittest.main()

