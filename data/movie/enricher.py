from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from tmdb_cache import load_tmdb_cache, save_tmdb_cache
from tmdb_client import TMDBClient


class MovieDataEnricher:
    """电影数据增强器（MovieLens + 可选 TMDB）。"""

    def __init__(
        self,
        tmdb_client: Optional[TMDBClient],
        cache_dir: Path,
        skip_optional: bool = False,
    ):
        self.tmdb_client = tmdb_client
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.skip_optional = skip_optional

        self.all_persons: Dict[int, Dict[str, Any]] = {}
        self.all_keywords: Dict[int, Dict[str, Any]] = {}
        self.all_companies: Dict[int, Dict[str, Any]] = {}
        self.all_countries: Dict[str, Dict[str, Any]] = {}
        self.all_languages: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _generate_description(movie_data: Dict[str, Any]) -> str:
        parts: List[str] = []

        if movie_data.get("name"):
            title = movie_data["name"]
            if movie_data.get("year"):
                title += f" ({movie_data['year']})"
            parts.append(title)

        genres = (
            movie_data.get("genres")
            or movie_data.get("tmdb_genres_raw")
            or movie_data.get("movielens_genres", [])
        )
        if genres:
            parts.append(f"类型: {', '.join(genres)}")

        overview = movie_data.get("overview")
        if overview:
            parts.append(overview)

        return " - ".join(parts)

    @staticmethod
    def _compute_rank_score(movie_data: Dict[str, Any]) -> Tuple[Optional[float], Optional[str], int]:
        ml_avg = movie_data.get("movielens_avg_rating")
        ml_cnt = int(movie_data.get("movielens_rating_count") or 0)
        tmdb_avg = movie_data.get("tmdb_vote_average")
        tmdb_cnt = int(movie_data.get("tmdb_vote_count") or 0)

        if ml_avg is not None and ml_cnt >= 50:
            return float(ml_avg) * 2.0, "movielens", ml_cnt
        if tmdb_avg is not None and tmdb_cnt > 0:
            return float(tmdb_avg), "tmdb", tmdb_cnt
        if ml_avg is not None:
            return float(ml_avg) * 2.0, "movielens", ml_cnt
        return None, None, 0

    @staticmethod
    def _append_unique(values: List[int], value: int) -> None:
        if value not in values:
            values.append(value)

    def enrich_movie(
        self,
        movie_row: pd.Series,
        links_row: pd.Series,
        rating_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        movie_id = int(movie_row["movieId"])
        tmdb_id = links_row["tmdbId"] if pd.notna(links_row.get("tmdbId")) else None

        enriched: Dict[str, Any] = {
            "movieId": movie_id,
            "name": movie_row["clean_title"],
            "year": int(movie_row["year"]) if pd.notna(movie_row.get("year")) else None,
            "movielens_genres_raw": movie_row.get("movielens_genres_raw", []),
            "movielens_genres": movie_row.get("movielens_genres", []),
            "movielens_genres_unmapped": movie_row.get("movielens_genres_unmapped", []),
            "tmdb_genres_raw": [],
            "genres": movie_row.get("movielens_genres", []),
            "imdbId": (
                f"tt{int(links_row['imdbId']):07d}"
                if pd.notna(links_row.get("imdbId"))
                else None
            ),
            "tmdbId": int(tmdb_id) if tmdb_id else None,
            "data_source": "movielens_only",
            "created_at": pd.Timestamp.utcnow().isoformat(),
        }

        if rating_stats:
            enriched["movielens_avg_rating"] = rating_stats.get("avg_rating")
            enriched["movielens_rating_count"] = int(rating_stats.get("rating_count", 0))

        # 未启用 TMDB（或无 tmdbId）时，直接返回基础数据
        if not self.tmdb_client or not tmdb_id:
            enriched["description"] = self._generate_description(enriched)
            score, source, votes = self._compute_rank_score(enriched)
            enriched["rank_score_0_10"] = score
            enriched["rank_score_source"] = source
            enriched["rank_score_votes"] = votes
            return enriched

        tmdb_id_int = int(tmdb_id)
        cache_file = self.cache_dir / f"movie_{tmdb_id_int}.json"
        cached_data = load_tmdb_cache(cache_file)

        if cached_data:
            enriched.update(cached_data)
            enriched["data_source"] = "movielens+tmdb"
        else:
            details = self.tmdb_client.get_movie_details(tmdb_id_int)
            if not details:
                enriched["description"] = self._generate_description(enriched)
                score, source, votes = self._compute_rank_score(enriched)
                enriched["rank_score_0_10"] = score
                enriched["rank_score_source"] = source
                enriched["rank_score_votes"] = votes
                return enriched

            tmdb_data: Dict[str, Any] = {
                "overview": details.get("overview"),
                "release_date": details.get("release_date"),
                "runtime": details.get("runtime"),
                "budget": details.get("budget"),
                "revenue": details.get("revenue"),
                "tmdb_vote_average": details.get("vote_average"),
                "tmdb_vote_count": details.get("vote_count"),
                "tmdb_popularity": details.get("popularity"),
                "original_language": details.get("original_language"),
                "poster_path": details.get("poster_path"),
                "backdrop_path": details.get("backdrop_path"),
                "tmdb_genres_raw": [g["name"] for g in details.get("genres", [])],
                "production_companies": [
                    {"id": c["id"], "name": c["name"], "origin_country": c.get("origin_country")}
                    for c in details.get("production_companies", [])
                ],
                "production_countries": [
                    {"code": c["iso_3166_1"], "name": c["name"]}
                    for c in details.get("production_countries", [])
                ],
                "spoken_languages": [
                    {"code": l["iso_639_1"], "name": l["name"]}
                    for l in details.get("spoken_languages", [])
                ],
            }

            credits = self.tmdb_client.get_movie_credits(tmdb_id_int)
            if credits:
                tmdb_data["cast"] = [
                    {
                        "personId": c["id"],
                        "name": c["name"],
                        "character": c.get("character"),
                        "order": c.get("order"),
                        "cast_id": c.get("cast_id"),
                        "popularity": c.get("popularity", 0),
                        "profile_path": c.get("profile_path", ""),
                    }
                    for c in credits.get("cast", [])[:20]
                ]

                tmdb_data["crew"] = [
                    {
                        "personId": c["id"],
                        "name": c["name"],
                        "job": c.get("job"),
                        "department": c.get("department"),
                        "popularity": c.get("popularity", 0),
                        "profile_path": c.get("profile_path", ""),
                    }
                    for c in credits.get("crew", [])
                    if c.get("job") == "Director"
                ]

            keywords = self.tmdb_client.get_movie_keywords(tmdb_id_int)
            if keywords:
                tmdb_data["keywords"] = [
                    {"id": k["id"], "name": k["name"]} for k in keywords.get("keywords", [])
                ]

            if not self.skip_optional:
                recs = self.tmdb_client.get_movie_recommendations(tmdb_id_int)
                if recs:
                    tmdb_data["recommendations"] = [
                        {
                            "tmdbId": r.get("id"),
                            "title": r.get("title") or r.get("name"),
                            "vote_average": r.get("vote_average"),
                            "vote_count": r.get("vote_count"),
                        }
                        for r in recs.get("results", [])[:20]
                        if r.get("id") is not None
                    ]

                sims = self.tmdb_client.get_movie_similar(tmdb_id_int)
                if sims:
                    tmdb_data["similar_movies"] = [
                        {
                            "tmdbId": r.get("id"),
                            "title": r.get("title") or r.get("name"),
                            "vote_average": r.get("vote_average"),
                            "vote_count": r.get("vote_count"),
                        }
                        for r in sims.get("results", [])[:20]
                        if r.get("id") is not None
                    ]

            save_tmdb_cache(tmdb_data, cache_file)
            enriched.update(tmdb_data)
            enriched["data_source"] = "movielens+tmdb"

        tmdb_genres = enriched.get("tmdb_genres_raw") or []
        enriched["genres"] = tmdb_genres if tmdb_genres else (enriched.get("movielens_genres") or [])

        enriched["description"] = self._generate_description(enriched)

        score, source, votes = self._compute_rank_score(enriched)
        enriched["rank_score_0_10"] = score
        enriched["rank_score_source"] = source
        enriched["rank_score_votes"] = votes

        self._aggregate_entities(enriched)
        return enriched

    def _aggregate_entities(self, movie_data: Dict[str, Any]) -> None:
        for person in movie_data.get("cast", []):
            person_id = int(person["personId"])
            if person_id not in self.all_persons:
                self.all_persons[person_id] = {
                    "personId": person_id,
                    "name": person.get("name"),
                    "person_type": "actor",
                    "popularity": person.get("popularity", 0),
                    "profile_path": person.get("profile_path", ""),
                    "movieIds": [],
                }
            self._append_unique(self.all_persons[person_id]["movieIds"], movie_data["movieId"])

        for person in movie_data.get("crew", []):
            person_id = int(person["personId"])
            if person_id not in self.all_persons:
                self.all_persons[person_id] = {
                    "personId": person_id,
                    "name": person.get("name"),
                    "person_type": "director",
                    "popularity": person.get("popularity", 0),
                    "profile_path": person.get("profile_path", ""),
                    "movieIds": [],
                }
            elif self.all_persons[person_id].get("person_type") == "actor":
                self.all_persons[person_id]["person_type"] = "both"
            self._append_unique(self.all_persons[person_id]["movieIds"], movie_data["movieId"])

        for kw in movie_data.get("keywords", []):
            kw_id = int(kw["id"])
            if kw_id not in self.all_keywords:
                self.all_keywords[kw_id] = {"keywordId": kw_id, "name": kw.get("name"), "movieIds": []}
            self._append_unique(self.all_keywords[kw_id]["movieIds"], movie_data["movieId"])

        for company in movie_data.get("production_companies", []):
            company_id = int(company["id"])
            if company_id not in self.all_companies:
                self.all_companies[company_id] = {
                    "companyId": company_id,
                    "name": company.get("name"),
                    "origin_country": company.get("origin_country"),
                    "movieIds": [],
                }
            self._append_unique(self.all_companies[company_id]["movieIds"], movie_data["movieId"])

        for country in movie_data.get("production_countries", []):
            code = country.get("code")
            if not code:
                continue
            if code not in self.all_countries:
                self.all_countries[code] = {"code": code, "name": country.get("name"), "movieIds": []}
            self._append_unique(self.all_countries[code]["movieIds"], movie_data["movieId"])

        for lang in movie_data.get("spoken_languages", []):
            code = lang.get("code")
            if not code:
                continue
            if code not in self.all_languages:
                self.all_languages[code] = {"code": code, "name": lang.get("name"), "movieIds": []}
            self._append_unique(self.all_languages[code]["movieIds"], movie_data["movieId"])

    def summarize_person_types(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for person in self.all_persons.values():
            counts[str(person.get("person_type") or "")] += 1
        return dict(counts)
