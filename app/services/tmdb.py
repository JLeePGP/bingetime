"""Minimal TMDB client for enrichment.

Auth is swap-safe: a v4 read-access token (JWT, starts with "eyJ") is sent as
a Bearer header; anything else is treated as a v3 API key query param. So the
free -> commercial-license upgrade is a pure .env change. Handles 429s with
Retry-After backoff so a rate/tier change won't crash a run.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from ..config import settings
from ..titles import normalize


@dataclass(frozen=True)
class ShowData:
    tmdb_id: str
    title: str
    seasons: int | None
    episodes: int | None
    avg_runtime_min: int | None
    poster_url: str | None
    total_runtime_min: int | None
    overview: str | None = None
    tmdb_rating: float | None = None
    release_year: int | None = None
    status: str | None = None


class TMDBError(RuntimeError):
    pass


class TMDBClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else settings.tmdb_api_key
        if not self.api_key:
            raise TMDBError("TMDB_API_KEY is not set")
        self._is_bearer = self.api_key.startswith("eyJ")
        headers = {"Accept": "application/json"}
        if self._is_bearer:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._client = httpx.Client(
            base_url=settings.tmdb_base_url, headers=headers, timeout=15.0
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TMDBClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, path: str, params: dict | None = None, _tries: int = 3) -> dict:
        params = dict(params or {})
        if not self._is_bearer:
            params["api_key"] = self.api_key
        for attempt in range(_tries):
            resp = self._client.get(path, params=params)
            if resp.status_code == 429 and attempt < _tries - 1:
                wait = int(resp.headers.get("Retry-After", "1")) + 1
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        raise TMDBError(f"rate-limited after {_tries} tries: {path}")

    def _poster(self, poster_path: str | None) -> str | None:
        if not poster_path:
            return None
        return f"{settings.tmdb_image_base}{poster_path}"

    @staticmethod
    def _year(date_str: str | None) -> int | None:
        """'2013-04-06' -> 2013; tolerant of empty/partial dates."""
        if not date_str or len(date_str) < 4 or not date_str[:4].isdigit():
            return None
        return int(date_str[:4])

    @staticmethod
    def _rating(vote_average) -> float | None:
        """TMDB reports 0.0 for unrated titles — treat that as unknown."""
        try:
            v = round(float(vote_average), 1)
        except (TypeError, ValueError):
            return None
        return v or None

    def search(
        self, title: str, media_type: str, prefer_ja: bool = False
    ) -> dict | None:
        """Best match for a title.

        Ranks by: exact title match first (this is what keeps 'Game of Thrones'
        from resolving to the more *popular* 'House of the Dragon', or
        'Dragon Ball' to 'Dragon Ball Z'), then Japanese-original for anime,
        then a prefix match, then popularity as the final tiebreaker.
        """
        endpoint = "/search/movie" if media_type == "movie" else "/search/tv"
        data = self._get(endpoint, {"query": title, "include_adult": "false"})
        results = data.get("results") or []
        if not results:
            return None

        q = normalize(title)

        def rank(r: dict) -> tuple:
            name = normalize(r.get("name") or r.get("title") or "")
            orig = normalize(r.get("original_name") or r.get("original_title") or "")
            exact = q in (name, orig)
            prefix = name.startswith(q) or (bool(name) and q.startswith(name))
            is_ja = r.get("original_language") == "ja"
            return (
                exact,
                is_ja if prefer_ja else False,
                prefix,
                r.get("popularity", 0),
            )

        results.sort(key=rank, reverse=True)
        return results[0]

    def _tv_avg_runtime(self, tmdb_id: str, detail: dict) -> int | None:
        """Series-level episode_run_time is often empty on TMDB now, so fall
        back to averaging the runtimes of a real season's episodes."""
        run_times = [r for r in (detail.get("episode_run_time") or []) if r]
        if run_times:
            return round(sum(run_times) / len(run_times))

        seasons = [
            s
            for s in (detail.get("seasons") or [])
            if (s.get("season_number") or 0) >= 1 and (s.get("episode_count") or 0) > 0
        ]
        if not seasons:
            return None
        first = min(seasons, key=lambda s: s["season_number"])
        season = self._get(f"/tv/{tmdb_id}/season/{first['season_number']}")
        eps = [e.get("runtime") for e in (season.get("episodes") or []) if e.get("runtime")]
        if not eps:
            return None
        return round(sum(eps) / len(eps))

    def details(self, tmdb_id: str, media_type: str) -> ShowData:
        if media_type == "movie":
            d = self._get(f"/movie/{tmdb_id}")
            runtime = d.get("runtime") or None
            return ShowData(
                tmdb_id=str(tmdb_id),
                title=d.get("title") or d.get("original_title") or "",
                seasons=1,
                episodes=1,
                avg_runtime_min=runtime,
                poster_url=self._poster(d.get("poster_path")),
                total_runtime_min=runtime,
                overview=d.get("overview") or None,
                tmdb_rating=self._rating(d.get("vote_average")),
                release_year=self._year(d.get("release_date")),
                status=d.get("status") or None,
            )

        d = self._get(f"/tv/{tmdb_id}")
        seasons = d.get("number_of_seasons")
        episodes = d.get("number_of_episodes")
        avg = self._tv_avg_runtime(str(tmdb_id), d)
        total = episodes * avg if (episodes and avg) else None
        return ShowData(
            tmdb_id=str(tmdb_id),
            title=d.get("name") or d.get("original_name") or "",
            seasons=seasons,
            episodes=episodes,
            avg_runtime_min=avg,
            poster_url=self._poster(d.get("poster_path")),
            total_runtime_min=total,
            overview=d.get("overview") or None,
            tmdb_rating=self._rating(d.get("vote_average")),
            release_year=self._year(d.get("first_air_date")),
            status=d.get("status") or None,
        )

    def top_ids(self, category: str, limit: int = 50) -> list[tuple[str, str]]:
        """Most-voted titles for a catalog category, as (tmdb_id, title) pairs.

        Uses /discover sorted by vote_count so we get well-known titles rather
        than obscure highly-rated ones. Genre 16 = Animation: anime is
        Japanese-language animation; the tv bucket excludes animation so it
        doesn't overlap anime.
        """
        media = "movie" if category == "movie" else "tv"
        params: dict = {"sort_by": "vote_count.desc", "include_adult": "false"}
        if category == "anime":
            params["with_genres"] = "16"
            params["with_original_language"] = "ja"
        elif category == "tv":
            params["without_genres"] = "16"

        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        page = 1
        while len(out) < limit and page <= 10:
            data = self._get(f"/discover/{media}", {**params, "page": page})
            results = data.get("results") or []
            if not results:
                break
            for r in results:
                tid = r.get("id")
                name = r.get("name") or r.get("title") or ""
                if tid is None or not name or str(tid) in seen:
                    continue
                seen.add(str(tid))
                out.append((str(tid), name))
                if len(out) >= limit:
                    break
            page += 1
        return out

    def fetch_by_title(self, title: str, category: str) -> ShowData | None:
        """category is the catalog value (movie/tv/anime); anime -> tv."""
        media_type = "movie" if category == "movie" else "tv"
        match = self.search(title, media_type, prefer_ja=(category == "anime"))
        if not match:
            return None
        tmdb_id = match.get("id")
        if tmdb_id is None:
            return None
        return self.details(str(tmdb_id), media_type)
