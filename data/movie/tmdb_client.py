import time
from typing import Dict, Optional

import requests


class TMDBClient:
    """TMDB API 客户端（鉴权/代理/限流/重试 + 端点封装）"""

    def __init__(
        self,
        api_token: str = "",
        api_key: str = "",
        rate_limit: float = 4.0,
        proxies: Optional[Dict] = None,
        base_url: str = "https://api.themoviedb.org/3",
    ):
        self.api_token = api_token
        self.api_key = api_key
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.last_request_time = 0.0
        self.proxies = proxies

        if api_token:
            self.headers = {
                "Authorization": f"Bearer {api_token}",
                "accept": "application/json",
            }
        else:
            self.headers = {"accept": "application/json"}

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self.last_request_time
        min_interval = 1.0 / self.rate_limit if self.rate_limit > 0 else 0.0
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        self._wait_for_rate_limit()

        url = f"{self.base_url}{endpoint}"

        if not self.api_token and self.api_key:
            params = params or {}
            params["api_key"] = self.api_key

        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                proxies=self.proxies,
                timeout=30,
            )

            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                print("触发限流 (429)，等待 10 秒后重试...")
                time.sleep(10)
                return self._make_request(endpoint, params)
            if response.status_code == 404:
                return None

            print(f"请求失败: {endpoint}, 状态码: {response.status_code}")
            return None
        except requests.RequestException as exc:
            print(f"网络错误: {endpoint}, {str(exc)}")
            return None

    def get_movie_details(self, tmdb_id: int) -> Optional[Dict]:
        return self._make_request(f"/movie/{tmdb_id}", params={"language": "en-US"})

    def get_movie_credits(self, tmdb_id: int) -> Optional[Dict]:
        return self._make_request(f"/movie/{tmdb_id}/credits", params={"language": "en-US"})

    def get_movie_keywords(self, tmdb_id: int) -> Optional[Dict]:
        return self._make_request(f"/movie/{tmdb_id}/keywords")

    def get_movie_recommendations(self, tmdb_id: int) -> Optional[Dict]:
        return self._make_request(
            f"/movie/{tmdb_id}/recommendations",
            params={"language": "en-US", "page": 1},
        )

    def get_movie_similar(self, tmdb_id: int) -> Optional[Dict]:
        return self._make_request(
            f"/movie/{tmdb_id}/similar",
            params={"language": "en-US", "page": 1},
        )

    def get_genre_list(self) -> Optional[Dict]:
        return self._make_request("/genre/movie/list", params={"language": "en"})

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        params = {
            "query": title,
            "include_adult": False,
            "language": "en-US",
            "page": 1,
        }
        if year:
            params["year"] = year
        return self._make_request("/search/movie", params=params)
