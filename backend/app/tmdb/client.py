"""Minimal TMDB v3 client (stdlib only, no extra deps).

Auth: set one of
  TMDB_API_KEY         -> v3 api_key query param
  TMDB_READ_TOKEN      -> v4 bearer token (Authorization header)

If neither is set, the client is in OFFLINE mode and callers should fall back to
fixtures (see fixtures.py). This keeps the whole pipeline runnable keyless.

Docs: https://developer.themoviedb.org/reference/discover-movie
      https://developer.themoviedb.org/reference/discover-tv
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

BASE = "https://api.themoviedb.org/3"


class TMDBError(RuntimeError):
    pass


@dataclass
class TMDBAuth:
    api_key: str | None
    read_token: str | None

    @property
    def offline(self) -> bool:
        return not (self.api_key or self.read_token)


def auth_from_env() -> TMDBAuth:
    return TMDBAuth(
        api_key=os.environ.get("TMDB_API_KEY"),
        read_token=os.environ.get("TMDB_READ_TOKEN"),
    )


class TMDBClient:
    """Thin GET client with pacing and simple retry on 429/5xx."""

    def __init__(self, auth: TMDBAuth | None = None, min_interval: float = 0.25):
        self.auth = auth or auth_from_env()
        self.min_interval = min_interval
        self._last = 0.0

    @property
    def offline(self) -> bool:
        return self.auth.offline

    def _pace(self) -> None:
        delta = time.monotonic() - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()

    def get(self, path: str, params: dict | None = None, _attempt: int = 0) -> dict:
        if self.offline:
            raise TMDBError("TMDBClient.get called in offline mode (no key/token)")
        params = dict(params or {})
        headers = {"Accept": "application/json"}
        if self.auth.read_token:
            headers["Authorization"] = f"Bearer {self.auth.read_token}"
        elif self.auth.api_key:
            params["api_key"] = self.auth.api_key

        url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers=headers)
        self._pace()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and _attempt < 4:
                retry_after = float(e.headers.get("Retry-After", 1)) if e.headers else 1.0
                time.sleep(min(retry_after, 5) * (_attempt + 1))
                return self.get(path, params, _attempt + 1)
            raise TMDBError(f"TMDB {e.code} for {path}: {e.read().decode()[:200]}") from e
        except urllib.error.URLError as e:
            raise TMDBError(f"TMDB network error for {path}: {e}") from e

    # ---- convenience wrappers ----

    def discover_movies(self, page: int = 1, **filters) -> dict:
        params = {
            "include_adult": "false",
            "include_video": "false",
            "language": "en-US",
            "sort_by": "popularity.desc",
            "page": page,
            **filters,
        }
        return self.get("/discover/movie", params)

    def discover_tv(self, page: int = 1, **filters) -> dict:
        params = {
            "include_adult": "false",
            "language": "en-US",
            "sort_by": "popularity.desc",
            "page": page,
            **filters,
        }
        return self.get("/discover/tv", params)

    def movie_alternative_titles(self, movie_id: int) -> dict:
        return self.get(f"/movie/{movie_id}/alternative_titles")

    def genre_movie_list(self) -> dict:
        return self.get("/genre/movie/list", {"language": "en-US"})

    def genre_tv_list(self) -> dict:
        return self.get("/genre/tv/list", {"language": "en-US"})
