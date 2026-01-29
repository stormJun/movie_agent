import unittest


class TestMiniProgramStreamMapping(unittest.TestCase):
    def test_map_start(self):
        from server.api.rest.v1.mp_chat_stream import _map_web_event_to_mp

        out = _map_web_event_to_mp({"status": "start", "request_id": "r1"}, request_id="fallback")
        self.assertEqual(out["type"], "generate_start")
        self.assertEqual(out["content"]["request_id"], "r1")

    def test_map_token(self):
        from server.api.rest.v1.mp_chat_stream import _map_web_event_to_mp

        out = _map_web_event_to_mp({"status": "token", "content": "Hi"}, request_id="r1")
        self.assertEqual(out, {"type": "chunk", "content": "Hi"})

    def test_map_done_content_is_falsy(self):
        from server.api.rest.v1.mp_chat_stream import _map_web_event_to_mp

        out = _map_web_event_to_mp({"status": "done", "request_id": "r1"}, request_id="fallback")
        self.assertEqual(out["type"], "complete")
        self.assertIsNone(out["content"])

    def test_map_unknown_ignored(self):
        from server.api.rest.v1.mp_chat_stream import _map_web_event_to_mp

        self.assertIsNone(_map_web_event_to_mp({"status": "execution_log"}, request_id="r1"))

    def test_map_progress_forwarded(self):
        from server.api.rest.v1.mp_chat_stream import _map_web_event_to_mp

        out = _map_web_event_to_mp(
            {"status": "progress", "content": {"stage": "retrieval", "completed": 0, "total": 1}},
            request_id="r1",
        )
        self.assertEqual(out["type"], "status")
        self.assertEqual(out["content"]["stage"], "retrieval")

    def test_map_recommendations(self):
        from server.api.rest.v1.mp_chat_stream import _map_web_event_to_mp

        out = _map_web_event_to_mp(
            {"status": "recommendations", "content": {"tmdb_ids": [1, 2]}}, request_id="r1"
        )
        self.assertEqual(out["type"], "recommendations")
        self.assertEqual(out["content"]["tmdb_ids"], [1, 2])


class TestMiniProgramMovieParsing(unittest.TestCase):
    def test_extract_directors_and_cast_and_genres(self):
        from server.api.rest.v1.mp_movies import _extract_directors, _extract_top_cast, _extract_genres

        raw = {
            "genres": [{"id": 1, "name": "Drama"}, {"id": 2, "name": "Romance"}],
            "credits": {
                "crew": [
                    {"job": "Director", "name": "Ang Lee"},
                    {"job": "Producer", "name": "Someone"},
                    {"job": "Director", "name": "Ang Lee"},  # duplicate
                ],
                "cast": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
            },
        }
        self.assertEqual(_extract_directors(raw), ["Ang Lee"])
        self.assertEqual(_extract_top_cast(raw, limit=2), ["A", "B"])
        self.assertEqual(_extract_genres(raw), ["Drama", "Romance"])


if __name__ == "__main__":
    unittest.main()
