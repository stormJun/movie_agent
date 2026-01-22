import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# MovieLens 到 TMDB 的类型映射
MOVIELENS_TO_TMDB_GENRE = {
    # 需要名称归一化的项（MovieLens → TMDB 规范名）
    "Children": "Family",
    "Sci-Fi": "Science Fiction",
    "Musical": "Music",
    # MovieLens 中不属于“类型”的项（不进入 :类型，保留在 unmapped 便于审计/回溯）
    "IMAX": None,
    "Film-Noir": None,
    "(no genres listed)": None,
}


class MovieLensParser:
    """MovieLens 数据解析器"""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            deduped.append(item)
        return deduped

    def _parse_genres(self, genre_str: str) -> Tuple[List[str], List[str], List[str]]:
        """
        解析并归一化 MovieLens genres

        Returns:
            (movielens_genres_raw, movielens_genres_canonical, movielens_genres_unmapped)
        """
        if pd.isna(genre_str) or not str(genre_str).strip():
            return [], [], []

        raw = str(genre_str).split("|")
        canonical: List[str] = []
        unmapped: List[str] = []

        for genre in raw:
            mapped = MOVIELENS_TO_TMDB_GENRE.get(genre, genre)
            if mapped is None:
                unmapped.append(genre)
            else:
                canonical.append(mapped)

        return (
            self._dedupe_keep_order(raw),
            self._dedupe_keep_order(canonical),
            self._dedupe_keep_order(unmapped),
        )

    def parse_movies(self) -> pd.DataFrame:
        """
        解析 movies.csv

        Returns:
            包含 movieId, clean_title, year, movielens_genres_raw, movielens_genres, movielens_genres_unmapped 的 DataFrame
        """
        movies_df = pd.read_csv(self.data_dir / "movies.csv")

        def extract_year_and_title(title: str) -> Tuple[str, Optional[int]]:
            match = re.search(r"^(.*?)\s*\((\d{4})\)$", title.strip())
            if match:
                return match.group(1).strip(), int(match.group(2))
            return title, None

        movies_df[["clean_title", "year"]] = movies_df["title"].apply(
            lambda x: pd.Series(extract_year_and_title(x))
        )

        parsed = movies_df["genres"].apply(self._parse_genres)
        movies_df["movielens_genres_raw"] = parsed.apply(lambda t: t[0])
        movies_df["movielens_genres"] = parsed.apply(lambda t: t[1])
        movies_df["movielens_genres_unmapped"] = parsed.apply(lambda t: t[2])

        return movies_df

    def parse_links(self) -> pd.DataFrame:
        """
        解析 links.csv

        Returns:
            包含 movieId, imdbId, tmdbId 的 DataFrame
        """
        return pd.read_csv(self.data_dir / "links.csv")

    def parse_ratings(self) -> Dict[int, Dict[str, float]]:
        """
        解析 ratings.csv 并聚合统计

        Returns:
            {movieId: {avg_rating, rating_count}}
        """
        print("正在读取和聚合评分数据...")
        ratings_df = pd.read_csv(self.data_dir / "ratings.csv")

        aggregated = (
            ratings_df.groupby("movieId")
            .agg({"rating": ["mean", "count"]})
            .reset_index()
        )
        aggregated.columns = ["movieId", "avg_rating", "rating_count"]

        return aggregated.set_index("movieId")[["avg_rating", "rating_count"]].to_dict(
            "index"
        )
