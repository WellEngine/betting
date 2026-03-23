from __future__ import annotations

from typing import Dict

from value_engine.data.api_football import get_team_missing_players


POSITION_WEIGHTS = {
    "Goalkeeper": 1.00,
    "Defender": 0.60,
    "Midfielder": 0.50,
    "Attacker": 0.70,
}

DEFAULT_WEIGHT = 0.35
MAX_PLAYER_IMPACT = 0.18


def _player_base_weight(player: dict) -> float:
    return POSITION_WEIGHTS.get(player.get("position"), DEFAULT_WEIGHT)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def get_player_impact(team_id: int, fixture_id: int) -> Dict:
    """
    Влияние отсутствующих игроков на атаку/защиту.

    Важно:
    этот модуль встроен в модель, но должен включаться
    только когда data-layer умеет качественно возвращать absences.
    """
    missing = get_team_missing_players(team_id, fixture_id)

    if not missing:
        return {
            "attack_modifier": 1.0,
            "defence_modifier": 1.0,
            "missing_players": 0,
            "key_absences": [],
        }

    attack_penalty = 0.0
    defence_penalty = 0.0
    key_absences = []

    for player in missing:
        base_weight = _player_base_weight(player)
        impact = _clamp(base_weight * 0.15, 0.05, MAX_PLAYER_IMPACT)

        attack_penalty += impact
        defence_penalty += impact * 0.8

        if base_weight >= 0.7 and player.get("name"):
            key_absences.append(player["name"])

    attack_penalty = _clamp(attack_penalty, 0.0, 0.35)
    defence_penalty = _clamp(defence_penalty, 0.0, 0.35)

    return {
        "attack_modifier": round(1.0 - attack_penalty, 3),
        "defence_modifier": round(1.0 + defence_penalty, 3),
        "missing_players": len(missing),
        "key_absences": key_absences,
    }
