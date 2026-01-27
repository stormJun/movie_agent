import unittest


class TestTmdbDisambiguationScoring(unittest.TestCase):
    def test_pick_best_candidate_prefers_exact_title_match(self) -> None:
        from infrastructure.enrichment.tmdb_client import _pick_best_candidate

        candidates = [
            {
                "id": 1,
                "title": "The Wedding Banquet",
                "original_title": "The Wedding Banquet",
                "release_date": "1993-08-04",
                "overview": "A long enough overview that should count as usable.",
                "vote_count": 10,
                "popularity": 1.0,
            },
            {
                "id": 2,
                "title": "Wedding Banquet",
                "original_title": "Wedding Banquet",
                "release_date": "2010-01-01",
                "overview": "",
                "vote_count": 10000,
                "popularity": 9999.0,
            },
        ]

        best, top = _pick_best_candidate(query_title="The Wedding Banquet", candidates=candidates, target_year=1993)
        self.assertIsNotNone(best)
        self.assertEqual(best.get("id"), 1)
        self.assertTrue(top)
        self.assertEqual(top[0].get("id"), 1)

    def test_pick_best_candidate_penalizes_year_mismatch(self) -> None:
        from infrastructure.enrichment.tmdb_client import _pick_best_candidate

        # Same title but wildly different years: prefer the closer year.
        candidates = [
            {
                "id": 10,
                "title": "喜宴",
                "original_title": "喜宴",
                "release_date": "2020-01-01",
                "overview": "x" * 50,
                "vote_count": 5000,
                "popularity": 500.0,
            },
            {
                "id": 11,
                "title": "喜宴",
                "original_title": "喜宴",
                "release_date": "1993-01-01",
                "overview": "x" * 50,
                "vote_count": 10,
                "popularity": 1.0,
            },
        ]

        best, _ = _pick_best_candidate(query_title="喜宴", candidates=candidates, target_year=1993)
        self.assertIsNotNone(best)
        self.assertEqual(best.get("id"), 11)

    def test_pick_best_person_candidate_prefers_exact_name_and_role_hint(self) -> None:
        from infrastructure.enrichment.tmdb_client import _pick_best_person_candidate

        candidates = [
            {
                "id": 1,
                "name": "李安",
                "original_name": "Ang Lee",
                "known_for_department": "Directing",
                "popularity": 10.0,
            },
            {
                "id": 2,
                "name": "李安",
                "original_name": "Li An",
                "known_for_department": "Acting",
                "popularity": 9999.0,  # shouldn't override role hint + exact match
            },
        ]

        best, top = _pick_best_person_candidate(
            query_name="李安", candidates=candidates, role_hint="Directing"
        )
        self.assertIsNotNone(best)
        self.assertEqual(best.get("id"), 1)
        self.assertTrue(top)
        self.assertEqual(top[0].get("id"), 1)

    def test_fallback_person_entity_extractor(self) -> None:
        from infrastructure.enrichment.entity_extractor import EntityExtractor

        got = EntityExtractor.extract_person_entities("李安导演了哪些电影？")
        self.assertTrue(got)
        self.assertEqual(got[0], "李安")

    def test_score_tv_candidate_prefers_exact_match_and_year(self) -> None:
        from infrastructure.enrichment.tmdb_client import _score_tv_candidate

        a = {
            "id": 1,
            "name": "琅琊榜",
            "original_name": "琅琊榜",
            "first_air_date": "2015-09-19",
            "overview": "x" * 50,
            "vote_count": 10,
            "popularity": 1.0,
        }
        b = {
            "id": 2,
            "name": "琅琊榜",
            "original_name": "琅琊榜",
            "first_air_date": "2020-01-01",
            "overview": "x" * 50,
            "vote_count": 10000,
            "popularity": 9999.0,
        }

        sa = _score_tv_candidate(query_title="琅琊榜", candidate=a, target_year=2015)
        sb = _score_tv_candidate(query_title="琅琊榜", candidate=b, target_year=2015)
        self.assertGreater(sa, sb)
