from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from functools import lru_cache
from typing import Iterable, List, Tuple

from value_engine.data.api_football import get_team_last_matches
from value_engine.data.leagues import get_league_config


REQUIRED_MATCHES = 15
MIN_CURRENT_SEASON_MATCHES = 8

RECENCY_DECAY = 0.92
PREVIOUS_SEASON_WEIGHT = 0.78


def _parse_match_date(match: dict) -> datetime:
    fixture = match.get("fixture", {})
    raw = fixture.get("date") or match.get("utcDate") or "1900-01-01T00:00:00+00:00"
    raw = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime(1900, 1, 1)


def _sort_recent_first(matches: Iterable[dict]) -> List[dict]:
    return sorted(matches, key=_parse_match_date, reverse=True)


def _match_weight(index: int, season_offset: int) -> float:
    return (RECENCY_DECAY ** index) * (PREVIOUS_SEASON_WEIGHT ** season_offset)


def _accumulate(stats: dict, match: dict, team_id: int, weight: float) -> None:
    home_id = match["homeTeam"]["id"]
    away_id = match["awayTeam"]["id"]

    goals = match.get("goals", {})
    goals_home = goals.get("home")
    goals_away = goals.get("away")

    if goals_home is None or goals_away is None:
        return

    stats["matches"] += 1
    stats["total_weight"] += weight

    if team_id == home_id:
        stats["gf_sum"] += goals_home * weight
        stats["ga_sum"] += goals_away * weight
        stats["gf_w"] += weight
        stats["ga_w"] += weight

        stats["home_matches"] += 1
        stats["home_gf_sum"] += goals_home * weight
        stats["home_ga_sum"] += goals_away * weight
        stats["home_w"] += weight

    elif team_id == away_id:
        stats["gf_sum"] += goals_away * weight
        stats["ga_sum"] += goals_home * weight
        stats["gf_w"] += weight
        stats["ga_w"] += weight

        stats["away_matches"] += 1
        stats["away_gf_sum"] += goals_away * weight
        stats["away_ga_sum"] += goals_home * weight
        stats["away_w"] += weight


def _wavg(total: float, weight: float) -> float:
    return round(total / weight, 3) if weight > 0 else 0.0


def _finalize(stats: dict) -> dict:
    return {
        "matches": int(stats["matches"]),
        "total_weight": round(stats["total_weight"], 3),
        "goals_for": _wavg(stats["gf_sum"], stats["gf_w"]),
        "goals_against": _wavg(stats["ga_sum"], stats["ga_w"]),
        "home_goals_for": _wavg(stats["home_gf_sum"], stats["home_w"]),
        "home_goals_against": _wavg(stats["home_ga_sum"], stats["home_w"]),
        "away_goals_for": _wavg(stats["away_gf_sum"], stats["away_w"]),
        "away_goals_against": _wavg(stats["away_ga_sum"], stats["away_w"]),
    }


@lru_cache(maxsize=128)
def get_team_stats(team_id: int, league_code: str) -> dict:
    league = get_league_config(league_code)
    if not league:
        return {}

    season_fn = league["season"]
    league_id = league["api_football_id"]

    current_season = season_fn()
    previous_season = current_season - 1

    current_matches = _sort_recent_first(
        get_team_last_matches(
            team_id=team_id,
            league_id=league_id,
            season=current_season,
            limit=REQUIRED_MATCHES,
        )
    )

    fallback_matches: List[dict] = []
    if len(current_matches) < MIN_CURRENT_SEASON_MATCHES:
        needed = REQUIRED_MATCHES - len(current_matches)
        fallback_matches = _sort_recent_first(
            get_team_last_matches(
                team_id=team_id,
                league_id=league_id,
                season=previous_season,
                limit=max(needed, 0),
            )
        )

    combined: List[Tuple[dict, int]] = [(m, 0) for m in current_matches]
    combined.extend((m, 1) for m in fallback_matches)

    stats = defaultdict(float)
    for idx, (match, season_offset) in enumerate(combined):
        weight = _match_weight(idx, season_offset)
        _accumulate(stats, match, team_id, weight)

    return _finalize(stats)
