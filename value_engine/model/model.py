from __future__ import annotations

from typing import Dict, List, Tuple

from value_engine.calibration.calibrator import calibrate_probability, load_calibration_models
from value_engine.data.api_football import get_fixture_odds
from value_engine.data.leagues import get_league_config
from value_engine.markets.mapper import map_market
from value_engine.model.player_impact import get_player_impact
from value_engine.model.poisson import calculate_totals_probabilities
from value_engine.model.team_stats import get_team_stats
from value_engine.settings import ENABLE_CALIBRATION, ENABLE_PLAYER_IMPACT, OFFLINE_DIR


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_metric(value: float | None, fallback: float) -> float:
    return value if isinstance(value, (int, float)) and value > 0 else fallback


def _build_lambda(*, team_stats: Dict, opp_stats: Dict, side: str, league_cfg: Dict) -> float:
    if side == "home":
        league_base = league_cfg["goal_avg_home"]
        gf = _safe_metric(team_stats.get("home_goals_for"), _safe_metric(team_stats.get("goals_for"), league_base))
        ga_opp = _safe_metric(opp_stats.get("away_goals_against"), _safe_metric(opp_stats.get("goals_against"), league_base))
        side_adjustment = league_cfg.get("home_advantage", 1.0)
    else:
        league_base = league_cfg["goal_avg_away"]
        gf = _safe_metric(team_stats.get("away_goals_for"), _safe_metric(team_stats.get("goals_for"), league_base))
        ga_opp = _safe_metric(opp_stats.get("home_goals_against"), _safe_metric(opp_stats.get("goals_against"), league_base))
        side_adjustment = 1.0

    attack_strength = gf / league_base
    defence_strength = ga_opp / league_base

    atk_lo, atk_hi = league_cfg["attack_clamp"]
    def_lo, def_hi = league_cfg["defence_clamp"]

    attack_strength = _clamp(attack_strength, atk_lo, atk_hi)
    defence_strength = _clamp(defence_strength, def_lo, def_hi)

    raw_lambda = league_base * attack_strength * defence_strength * side_adjustment
    return round(_clamp(raw_lambda, league_cfg["min_lambda"], league_cfg["max_lambda"]), 3)


def _apply_player_impact(
    *,
    match_id: int,
    home_team_id: int,
    away_team_id: int,
    lambda_home: float,
    lambda_away: float,
    league_cfg: Dict,
) -> Tuple[float, float, Dict]:
    """
    Фича реализована, но выключена по умолчанию.

    Причина:
    пока нет качественного production-парсинга absences,
    модификация lambda может больше навредить, чем помочь.

    Когда появится нормальный источник составов:
    1) включаете VALUE_ENGINE_ENABLE_PLAYER_IMPACT=1
    2) реализуете get_team_missing_players(...)
    3) проверяете на бэктесте, что качество реально выросло
    """
    if not ENABLE_PLAYER_IMPACT:
        return lambda_home, lambda_away, {"enabled": False}

    home_impact = get_player_impact(home_team_id, match_id)
    away_impact = get_player_impact(away_team_id, match_id)

    lambda_home_adj = lambda_home * home_impact["attack_modifier"] * away_impact["defence_modifier"]
    lambda_away_adj = lambda_away * away_impact["attack_modifier"] * home_impact["defence_modifier"]

    lambda_home_adj = round(_clamp(lambda_home_adj, league_cfg["min_lambda"], league_cfg["max_lambda"]), 3)
    lambda_away_adj = round(_clamp(lambda_away_adj, league_cfg["min_lambda"], league_cfg["max_lambda"]), 3)

    return lambda_home_adj, lambda_away_adj, {
        "enabled": True,
        "home": home_impact,
        "away": away_impact,
    }


def calculate_confidence(market: Dict, expected_goals: Dict) -> float:
    prob = float(market["probability"])
    odds = float(market["odds"])
    market_key = market["market"]

    lambda_total = expected_goals["home"] + expected_goals["away"]

    prob_score = _clamp(prob, 0.0, 1.0)

    if odds < 1.20:
        odds_score = 0.40
    elif odds > 3.50:
        odds_score = 0.50
    else:
        odds_score = 1.00

    if market_key == "over_1_5":
        lambda_score = _clamp(lambda_total / 2.2, 0.0, 1.0)
    elif market_key == "under_1_5":
        lambda_score = _clamp((1.9 - lambda_total) / 1.0, 0.0, 1.0)
    elif market_key == "over_2_5":
        lambda_score = _clamp(lambda_total / 3.2, 0.0, 1.0)
    elif market_key == "under_2_5":
        lambda_score = _clamp((3.0 - lambda_total) / 1.2, 0.0, 1.0)
    elif market_key == "under_3_5":
        lambda_score = _clamp((4.0 - lambda_total) / 1.4, 0.0, 1.0)
    else:
        lambda_score = 0.70

    confidence = (0.50 * prob_score) + (0.30 * lambda_score) + (0.20 * odds_score)
    return round(_clamp(confidence, 0.0, 1.0), 3)


def predict_match(
    *,
    match_id: int,
    league_code: str,
    home_team_id: int,
    away_team_id: int,
    home_team_name: str,
    away_team_name: str,
) -> Dict:
    empty = {"match_id": match_id, "markets": []}

    home_stats = get_team_stats(home_team_id, league_code)
    away_stats = get_team_stats(away_team_id, league_code)
    if not home_stats or not away_stats:
        return empty

    league_cfg = get_league_config(league_code)

    lambda_home = _build_lambda(
        team_stats=home_stats,
        opp_stats=away_stats,
        side="home",
        league_cfg=league_cfg,
    )
    lambda_away = _build_lambda(
        team_stats=away_stats,
        opp_stats=home_stats,
        side="away",
        league_cfg=league_cfg,
    )

    lambda_home, lambda_away, impact_info = _apply_player_impact(
        match_id=match_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        lambda_home=lambda_home,
        lambda_away=lambda_away,
        league_cfg=league_cfg,
    )

    poisson = calculate_totals_probabilities(
        lambda_home=lambda_home,
        lambda_away=lambda_away,
    )

    expected_goals = {
        "home": lambda_home,
        "away": lambda_away,
        "total": round(lambda_home + lambda_away, 3),
    }

    probs = poisson.get("totals", {})
    odds_map = get_fixture_odds(match_id)
    if not odds_map:
        return empty

    calibration_models = load_calibration_models() if ENABLE_CALIBRATION else {}

    markets_out: List[Dict] = []
    for market_key, raw_prob in probs.items():
        odds = odds_map.get(market_key)
        if not odds:
            continue

        prob = calibrate_probability(market_key, raw_prob, calibration_models) if ENABLE_CALIBRATION else raw_prob
        fair_odds = 1.0 / prob if prob > 0 else None
        value = round((prob * odds) - 1.0, 4)
        edge = round(odds - fair_odds, 4) if fair_odds else None
        edge_percent = round((odds / fair_odds) - 1.0, 4) if fair_odds else None

        confidence = calculate_confidence(
            {"market": market_key, "probability": prob, "odds": odds},
            expected_goals,
        )

        markets_out.append(
            map_market(
                market=market_key,
                probability=prob,
                raw_probability=raw_prob,
                odds=float(odds),
                fair_odds=fair_odds,
                edge=edge,
                edge_percent=edge_percent,
                value=value,
                confidence=confidence,
                source="offline" if OFFLINE_DIR is not None else "api_football",
                calibration_applied=bool(ENABLE_CALIBRATION and market_key in calibration_models),
            )
        )

    if not markets_out:
        return empty

    markets_out.sort(key=lambda item: (item["value"], item["confidence"]), reverse=True)

    return {
        "match_id": match_id,
        "league": league_code,
        "home": home_team_name,
        "away": away_team_name,
        "expected_goals": expected_goals,
        "player_impact": impact_info,
        "markets": markets_out,
    }
