from __future__ import annotations

from typing import Dict, List

from value_engine.model.model import predict_match
from value_engine.roi.tracker import track_market


DEBUG = False

MAX_MATCHES_DEFAULT = 30
MAX_MARKETS_PER_MATCH = 3


def is_safe_market(*, market: Dict, expected_goals: Dict) -> tuple[bool, str]:
    key = market["market"]
    prob = float(market["probability"])
    odds = float(market["odds"])

    lambda_home = expected_goals["home"]
    lambda_away = expected_goals["away"]
    lambda_total = lambda_home + lambda_away
    lambda_gap = abs(lambda_home - lambda_away)

    if key == "under_3_5":
        if lambda_total > 3.40:
            return False, "lambda_total > 3.40"
        if prob < 0.55:
            return False, "prob < 0.55"
        if not (1.25 <= odds <= 2.10):
            return False, "odds out of range"
        if lambda_gap > 1.55:
            return False, "lambda_gap > 1.55"
        return True, "OK"

    if key == "under_2_5":
        if lambda_total > 2.55:
            return False, "lambda_total > 2.55"
        if prob < 0.60:
            return False, "prob < 0.60"
        if not (1.45 <= odds <= 2.20):
            return False, "odds out of range"
        if lambda_gap > 0.90:
            return False, "lambda_gap > 0.90"
        return True, "OK"

    # В safe-профиле deliberately не оставляем мёртвые или спорные рынки.
    return False, "market_not_safe_type"


def _collect_matches(fixtures: List[Dict], *, limit: int) -> List[Dict]:
    results: List[Dict] = []

    for fixture in fixtures:
        league_code = fixture["league_code"]
        prediction = predict_match(
            match_id=fixture["id"],
            league_code=league_code,
            home_team_id=fixture["homeTeam"]["id"],
            away_team_id=fixture["awayTeam"]["id"],
            home_team_name=fixture["homeTeam"]["name"],
            away_team_name=fixture["awayTeam"]["name"],
        )

        markets = prediction.get("markets", [])
        if not markets:
            continue

        expected_goals = prediction["expected_goals"]
        safe_markets: List[Dict] = []

        for market in markets:
            ok, _reason = is_safe_market(market=market, expected_goals=expected_goals)
            if ok:
                market["indicator"] = "🛡️"
                safe_markets.append(market)

        if not safe_markets:
            continue

        safe_markets.sort(
            key=lambda item: (item.get("confidence", 0.0), item.get("probability", 0.0)),
            reverse=True,
        )

        results.append(
            {
                "match_id": fixture["id"],
                "league": league_code,
                "home": fixture["homeTeam"]["name"],
                "away": fixture["awayTeam"]["name"],
                "utcDate": fixture["utcDate"],
                "expected_goals": expected_goals,
                "player_impact": prediction.get("player_impact", {}),
                "markets": safe_markets[:MAX_MARKETS_PER_MATCH],
            }
        )

        for market in safe_markets[:MAX_MARKETS_PER_MATCH]:
            track_market(
                match={
                    "match_id": fixture["id"],
                    "league": league_code,
                    "home": fixture["homeTeam"]["name"],
                    "away": fixture["awayTeam"]["name"],
                    "utcDate": fixture["utcDate"],
                },
                market=market,
                value_type="safe",
            )

        if len(results) >= limit:
            break

    return results


def find_safe_picks(fixtures: List[Dict], *, limit: int = MAX_MATCHES_DEFAULT) -> List[Dict]:
    return _collect_matches(fixtures=fixtures, limit=limit)
