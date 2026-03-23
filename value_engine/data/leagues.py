from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Dict


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def european_season() -> int:
    now = _utc_now()
    return now.year if now.month >= 7 else now.year - 1


def calendar_year_season() -> int:
    return _utc_now().year


DEFAULT_LEAGUE = {
    "api_football_id": 0,
    "season": european_season,
    "goal_avg_home": 1.42,
    "goal_avg_away": 1.18,
    "home_advantage": 1.06,
    "min_lambda": 0.45,
    "max_lambda": 2.85,
    "attack_clamp": (0.55, 1.70),
    "defence_clamp": (0.55, 1.70),
}

# Эти параметры — стартовые priors.
# Их нужно валидировать и тюнить на ваших исторических данных.
LEAGUES: Dict[str, Dict] = {
    "EPL": {
        "api_football_id": 39,
        "season": european_season,
        "goal_avg_home": 1.58,
        "goal_avg_away": 1.30,
        "home_advantage": 1.07,
        "min_lambda": 0.45,
        "max_lambda": 2.90,
        "attack_clamp": (0.55, 1.70),
        "defence_clamp": (0.55, 1.70),
    },
    "LL": {
        "api_football_id": 140,
        "season": european_season,
        "goal_avg_home": 1.48,
        "goal_avg_away": 1.12,
        "home_advantage": 1.08,
        "min_lambda": 0.42,
        "max_lambda": 2.75,
        "attack_clamp": (0.55, 1.65),
        "defence_clamp": (0.55, 1.65),
    },
    "SA": {
        "api_football_id": 135,
        "season": european_season,
        "goal_avg_home": 1.44,
        "goal_avg_away": 1.16,
        "home_advantage": 1.07,
        "min_lambda": 0.42,
        "max_lambda": 2.80,
        "attack_clamp": (0.55, 1.65),
        "defence_clamp": (0.55, 1.65),
    },
    "BUN": {
        "api_football_id": 78,
        "season": european_season,
        "goal_avg_home": 1.72,
        "goal_avg_away": 1.42,
        "home_advantage": 1.05,
        "min_lambda": 0.48,
        "max_lambda": 3.05,
        "attack_clamp": (0.55, 1.75),
        "defence_clamp": (0.55, 1.75),
    },
    "L1": {
        "api_football_id": 61,
        "season": european_season,
        "goal_avg_home": 1.43,
        "goal_avg_away": 1.11,
        "home_advantage": 1.07,
        "min_lambda": 0.42,
        "max_lambda": 2.72,
        "attack_clamp": (0.55, 1.60),
        "defence_clamp": (0.55, 1.60),
    },
    "MLS": {
        "api_football_id": 253,
        "season": calendar_year_season,
        "goal_avg_home": 1.68,
        "goal_avg_away": 1.33,
        "home_advantage": 1.09,
        "min_lambda": 0.50,
        "max_lambda": 3.05,
        "attack_clamp": (0.55, 1.80),
        "defence_clamp": (0.55, 1.80),
    },
    "BRA": {
        "api_football_id": 71,
        "season": calendar_year_season,
        "goal_avg_home": 1.30,
        "goal_avg_away": 0.99,
        "home_advantage": 1.10,
        "min_lambda": 0.40,
        "max_lambda": 2.55,
        "attack_clamp": (0.55, 1.55),
        "defence_clamp": (0.55, 1.55),
    },
    "J1": {
        "api_football_id": 98,
        "season": calendar_year_season,
        "goal_avg_home": 1.34,
        "goal_avg_away": 1.09,
        "home_advantage": 1.06,
        "min_lambda": 0.40,
        "max_lambda": 2.65,
        "attack_clamp": (0.55, 1.60),
        "defence_clamp": (0.55, 1.60),
    },
}


def get_league_config(league_code: str) -> Dict:
    return {**DEFAULT_LEAGUE, **LEAGUES.get(league_code, {})}
