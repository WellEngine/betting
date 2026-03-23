from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import requests

from value_engine.settings import API_FOOTBALL_BASE_URL, API_FOOTBALL_KEY, OFFLINE_DIR


SUPPORTED_MARKETS = {
    "over_1_5",
    "under_1_5",
    "over_2_5",
    "under_2_5",
    "under_3_5",
}

BET_NAME_ALIASES = {
    "Goals Over/Under": "totals",
    "Goals O/U": "totals",
    "Over/Under": "totals",
}

# Инициализируем сессию для переиспользования TCP-соединений
_SESSION = requests.Session()


def _offline_path(name: str) -> Path | None:
    if OFFLINE_DIR is None:
        return None
    return OFFLINE_DIR / name


@lru_cache(maxsize=1)
def _load_offline_team_matches() -> Dict[str, List[dict]]:
    path = _offline_path("team_matches.json")
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_offline_odds() -> Dict[str, Dict[str, float]]:
    path = _offline_path("odds.json")
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_offline_missing_players() -> Dict[str, List[dict]]:
    path = _offline_path("missing_players.json")
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _headers() -> Dict[str, str]:
    if not API_FOOTBALL_KEY:
        raise RuntimeError("API_FOOTBALL_KEY is empty. Set .env or use VALUE_ENGINE_OFFLINE_DIR.")
    return {
        "x-apisports-key": API_FOOTBALL_KEY,
    }


def _get(endpoint: str, params: Dict) -> Dict:
    response = _SESSION.get(
        f"{API_FOOTBALL_BASE_URL}/{endpoint.lstrip('/')}",
        headers=_headers(),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_team_last_matches(*, team_id: int, league_id: int, season: int, limit: int = 15) -> List[dict]:
    if OFFLINE_DIR is not None:
        key = f"{league_id}:{season}:{team_id}"
        return _load_offline_team_matches().get(key, [])[:limit]

    payload = _get(
        "fixtures",
        {
            "team": team_id,
            "league": league_id,
            "season": season,
            "last": limit,
        },
    )

    matches = []
    for item in payload.get("response", []):
        goals = item.get("goals", {})
        teams = item.get("teams", {})
        fixture = item.get("fixture", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        matches.append(
            {
                "fixture": {"date": fixture.get("date")},
                "homeTeam": {"id": home.get("id"), "name": home.get("name")},
                "awayTeam": {"id": away.get("id"), "name": away.get("name")},
                "goals": {"home": goals.get("home"), "away": goals.get("away")},
            }
        )

    return matches


def _normalise_total_market(value: str) -> str | None:
    raw = str(value).strip().lower().replace(" ", "")
    mapping = {
        "over1.5": "over_1_5",
        "under1.5": "under_1_5",
        "over2.5": "over_2_5",
        "under2.5": "under_2_5",
        "under3.5": "under_3_5",
    }
    return mapping.get(raw)


def get_fixture_odds(match_id: int) -> Dict[str, float]:
    if OFFLINE_DIR is not None:
        return _load_offline_odds().get(str(match_id), {})

    payload = _get("odds", {"fixture": match_id})

    best: Dict[str, float] = {}
    for response_item in payload.get("response", []):
        bookmakers = response_item.get("bookmakers", [])
        for bookmaker in bookmakers:
            for bet in bookmaker.get("bets", []):
                bet_name = bet.get("name")
                if BET_NAME_ALIASES.get(bet_name) != "totals":
                    continue

                for option in bet.get("values", []):
                    market_key = _normalise_total_market(option.get("value"))
                    odd = option.get("odd")
                    if market_key not in SUPPORTED_MARKETS or odd in {None, ""}:
                        continue
                    odd = float(odd)
                    best[market_key] = max(best.get(market_key, 0.0), odd)

    return best


def get_team_missing_players(team_id: int, fixture_id: int) -> List[dict]:
    if OFFLINE_DIR is not None:
        key = f"{fixture_id}:{team_id}"
        return _load_offline_missing_players().get(key, [])

    return []
