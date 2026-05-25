import asyncio
import hashlib
import json
from datetime import datetime, timezone

import httpx

from src.schemas import Article
from src.utils import DiskCache, get_logger

_BASE = "https://stats.nba.com/stats/leaguegamelog"
_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.nba.com/",
}


class NBAStatsFetcher:
    def __init__(self, cache_dir: str = "data/.cache/nba_stats") -> None:
        self._cache = DiskCache(cache_dir)
        self._log = get_logger(__name__)

    def _fetch_raw(self, params: dict) -> dict:
        cache_key = f"nba_stats:{json.dumps(params, sort_keys=True)}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)
        with httpx.Client(headers=_HEADERS, timeout=30) as client:
            resp = client.get(_BASE, params=params)
            resp.raise_for_status()
            self._cache.set(cache_key, resp.content)
            return resp.json()

    def _rows_to_articles(self, data: dict) -> list[Article]:
        rs = data["resultSets"][0]
        idx = {h: i for i, h in enumerate(rs["headers"])}

        games: dict[str, list] = {}
        for row in rs["rowSet"]:
            games.setdefault(row[idx["GAME_ID"]], []).append(row)

        articles = []
        for gid, rows in games.items():
            home = next((r for r in rows if "vs." in r[idx["MATCHUP"]]), rows[0])
            away = next(
                (r for r in rows if "@" in r[idx["MATCHUP"]]),
                rows[-1] if len(rows) > 1 else rows[0],
            )

            home_team = home[idx["TEAM_NAME"]]
            away_team = away[idx["TEAM_NAME"]]
            home_score = home[idx["PTS"]]
            away_score = away[idx["PTS"]]
            game_date = home[idx["GAME_DATE"]]

            if home[idx["WL"]] == "W":
                winner, loser, ws, ls = home_team, away_team, home_score, away_score
            else:
                winner, loser, ws, ls = away_team, home_team, away_score, home_score

            url = f"https://www.nba.com/game/{gid}"
            try:
                pub_date = datetime.strptime(game_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, tzinfo=timezone.utc
                )
            except ValueError:
                pub_date = None

            articles.append(Article(
                article_id=hashlib.sha256(url.encode()).hexdigest(),
                source="nba_stats",
                url=url,
                published_at=pub_date,
                timestamp_precision="day",  # game date only — never "minute"
                title=f"{home_team} {home_score} - {away_score} {away_team} ({game_date})",
                lede=f"Game result: {winner} defeated {loser} {ws}-{ls}",
                body_text=None,
                text_available=False,
                entities=[home_team, away_team],
                themes=["SPORTS", "BASKETBALL_NBA"],
                raw_metadata_json=json.dumps({
                    "game_id": gid,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "game_date": game_date,
                }),
            ))

        return articles

    async def fetch_game_events(self, season: str = "2024-25") -> list[Article]:
        """Fetch Regular Season and Playoffs game logs, return as Article stubs."""
        loop = asyncio.get_running_loop()
        articles = []
        for season_type in ["Regular Season", "Playoffs"]:
            params = {
                "LeagueID": "00",
                "Season": season,
                "SeasonType": season_type,
                "Counter": "0",
                "Direction": "ASC",
                "PlayerOrTeam": "T",
                "Sorter": "DATE",
                "DateFrom": "",
                "DateTo": "",
            }
            try:
                # _fetch_raw blocks on network I/O; run in thread pool to avoid blocking event loop
                data = await loop.run_in_executor(None, lambda p=params: self._fetch_raw(p))
                articles.extend(self._rows_to_articles(data))
            except Exception as exc:
                self._log.warning(
                    "nba stats fetch failed",
                    extra={"season_type": season_type, "error": str(exc)},
                )

        self._log.info("nba_stats done", extra={"count": len(articles)})
        return articles
