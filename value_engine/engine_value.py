from __future__ import annotations

import logging
from typing import Dict, List

from value_engine.model.model import predict_match
from value_engine.roi.tracker import track_markets_batch


logger = logging.getLogger("engine_value")

DEBUG = False

MAX_MATCHES_DEFAULT = 30
MAX_MARKETS_PER_MATCH = 3

VALUE_PRIORITY = {
    "core": 2,
    "plus": 1,
}


def _collect_matches(fixtures: List[Dict], *, limit: int) -> List[Dict]:
    results: List[Dict] = []
    prediction_cache: Dict[int, Dict] = {}
    picks_to_track: List[Dict] = []  # Буфер для пакетного сохранения

    for fixture in fixtures:
        match_id = fixture["id"]
        league_code = fixture["league_code"]

        if match_id not in prediction_cache:
            prediction_cache[match_id] = predict_match(
                match_id=match_id,
                league_code=league_code,
                home_team_id=fixture["homeTeam"]["id"],
                away_team_id=fixture["awayTeam"]["id"],
                home_team_name=fixture["homeTeam"]["name"],
                away_team_name=fixture["awayTeam"]["name"],
            )

        prediction = prediction_cache[match_id]
        markets = prediction.get("markets", [])
        if not markets:
            continue

        expected_goals = prediction["expected_goals"]
        lambda_total = expected_goals["total"]

        value_markets: List[Dict] = []
        for market in markets:
            key = market["market"]
            prob = float(market["probability"])
            odds = float(market["odds"])
            value = market.get("value")
            if value is None:
                continue

            # Только рынки, которые модель реально считает.
            if key == "over_2_5":
                if lambda_total >= 2.70 and prob >= 0.52 and odds >= 1.60 and value >= 0.03:
                    market["value_type"] = "core"
                    market["indicator"] = "💎"
                    value_markets.append(market)

            elif key == "under_2_5":
                if lambda_total <= 2.35 and prob >= 0.53 and odds >= 1.60 and value >= 0.04:
                    market["value_type"] = "plus"
                    market["indicator"] = "💰"
                    value_markets.append(market)

            elif key == "under_3_5":
                if lambda_total <= 3.05 and prob >= 0.58 and odds >= 1.45 and value >= 0.03:
                    market["value_type"] = "plus"
                    market["indicator"] = "💰"
                    value_markets.append(market)

        if not value_markets:
            continue

        value_markets.sort(
            key=lambda item: (
                VALUE_PRIORITY.get(item.get("value_type", ""), 0),
                item.get("value", 0.0),
                item.get("confidence", 0.0),
            ),
            reverse=True,
        )
        value_markets = value_markets[:MAX_MARKETS_PER_MATCH]

        match_row = {
            "match_id": match_id,
            "league": league_code,
            "home": fixture["homeTeam"]["name"],
            "away": fixture["awayTeam"]["name"],
            "utcDate": fixture["utcDate"],
            "expected_goals": expected_goals,
            "player_impact": prediction.get("player_impact", {}),
            "markets": value_markets,
            "max_value": value_markets[0]["value"],
        }
        results.append(match_row)

        match_metadata = {
            "match_id": match_id,
            "league": league_code,
            "home": fixture["homeTeam"]["name"],
            "away": fixture["awayTeam"]["name"],
            "utcDate": fixture["utcDate"],
        }

        for market in value_markets:
            picks_to_track.append({
                "match": match_metadata,
                "market": market,
                "value_type": market.get("value_type", "core")
            })

        if DEBUG:
            logger.info("VALUE | %s vs %s | %s", match_row["home"], match_row["away"], value_markets)

        if len(results) >= limit:
            break

    # Единоразовая запись всех рынков на диск
    if picks_to_track:
        track_markets_batch(picks_to_track)

    return results


def find_value_picks(fixtures: List[Dict], *, limit: int = MAX_MATCHES_DEFAULT) -> List[Dict]:
    return _collect_matches(fixtures=fixtures, limit=limit)
