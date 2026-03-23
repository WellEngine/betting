from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from value_engine.settings import TRACKED_PICKS_FILE


SUPPORTED_MARKETS = {
    "over_1_5",
    "under_1_5",
    "over_2_5",
    "under_2_5",
    "under_3_5",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_rows(path: Path | None = None) -> List[dict]:
    path = path or TRACKED_PICKS_FILE
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_rows(rows: List[dict], path: Path | None = None) -> Path:
    path = path or TRACKED_PICKS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _pick_id(match_id: int, market: str, value_type: str) -> str:
    return f"{match_id}:{market}:{value_type}"


def _upsert_row(rows: List[dict], row: dict) -> dict:
    for idx, existing in enumerate(rows):
        if existing.get("pick_id") == row["pick_id"]:
            rows[idx] = {**existing, **row, "updated_at": _utc_now_iso()}
            return rows[idx]
    row["created_at"] = _utc_now_iso()
    row["updated_at"] = row["created_at"]
    rows.append(row)
    return row


def track_markets_batch(picks_data: List[Dict], path: Path | None = None) -> List[dict]:
    """Пакетное сохранение рынков (решает проблему O(N^2) записи на диск)"""
    rows = _load_rows(path)
    saved_picks = []
    
    for item in picks_data:
        match = item["match"]
        market = item["market"]
        value_type = item["value_type"]
        
        if market.get("market") not in SUPPORTED_MARKETS:
            continue

        pick = {
            "pick_id": _pick_id(match["match_id"], market["market"], value_type),
            "match_id": match["match_id"],
            "league": match.get("league"),
            "home": match.get("home"),
            "away": match.get("away"),
            "utcDate": match.get("utcDate"),
            "market": market["market"],
            "value_type": value_type,
            "raw_probability": market.get("raw_probability"),
            "probability": market.get("probability"),
            "calibration_applied": market.get("calibration_applied", False),
            "odds_picked": market.get("odds"),
            "fair_odds": market.get("fair_odds"),
            "edge": market.get("edge"),
            "edge_percent": market.get("edge_percent"),
            "value": market.get("value"),
            "confidence": market.get("confidence"),
            "closing_odds": None,
            "clv_pct": None,
            "clv_implied_shift": None,
            "result": None,
            "profit_units": None,
        }
        saved = _upsert_row(rows, pick)
        saved_picks.append(saved)
        
    if saved_picks:
        _save_rows(rows, path)
        
    return saved_picks


def track_market(*, match: Dict, market: Dict, value_type: str, path: Path | None = None) -> dict:
    """Оставлено для обратной совместимости. Рекомендуется использовать track_markets_batch."""
    res = track_markets_batch([{"match": match, "market": market, "value_type": value_type}], path)
    return res[0] if res else {}


def load_tracked_picks(path: Path | None = None) -> List[dict]:
    return _load_rows(path)


def update_closing_lines(closing_rows: Iterable[dict], path: Path | None = None) -> Path:
    rows = _load_rows(path)
    closing_rows = list(closing_rows)

    for row in rows:
        for closing in closing_rows:
            same_match = closing.get("match_id") == row.get("match_id")
            same_market = closing.get("market") == row.get("market")
            if not (same_match and same_market):
                continue

            closing_odds = float(closing["closing_odds"])
            row["closing_odds"] = closing_odds

            picked_odds = float(row["odds_picked"])
            if closing_odds > 0 and picked_odds > 0:
                row["clv_pct"] = round((picked_odds / closing_odds) - 1.0, 4)
                row["clv_implied_shift"] = round((1.0 / closing_odds) - (1.0 / picked_odds), 4)
            row["updated_at"] = _utc_now_iso()

    return _save_rows(rows, path)


def _resolve_total_goals(result_row: dict) -> int | None:
    if "total_goals" in result_row:
        return int(result_row["total_goals"])
    goals = result_row.get("goals") or {}
    home = goals.get("home")
    away = goals.get("away")
    if home is None or away is None:
        return None
    return int(home) + int(away)


def _settle_market(market: str, total_goals: int) -> int | None:
    if market == "over_1_5":
        return int(total_goals >= 2)
    if market == "under_1_5":
        return int(total_goals <= 1)
    if market == "over_2_5":
        return int(total_goals >= 3)
    if market == "under_2_5":
        return int(total_goals <= 2)
    if market == "under_3_5":
        return int(total_goals <= 3)
    return None


def settle_picks(results: Iterable[dict], path: Path | None = None) -> Path:
    rows = _load_rows(path)
    results = list(results)

    for row in rows:
        for result_row in results:
            if result_row.get("match_id") != row.get("match_id"):
                continue

            total_goals = _resolve_total_goals(result_row)
            if total_goals is None:
                continue

            outcome = _settle_market(row["market"], total_goals)
            if outcome is None:
                continue

            row["result"] = outcome
            picked_odds = float(row["odds_picked"])
            row["profit_units"] = round((picked_odds - 1.0) if outcome == 1 else -1.0, 4)
            row["updated_at"] = _utc_now_iso()

    return _save_rows(rows, path)


def build_performance_summary(rows: Iterable[dict] | None = None) -> dict:
    rows = list(rows) if rows is not None else _load_rows()
    settled = [r for r in rows if r.get("result") in {0, 1}]
    clv_rows = [r for r in rows if isinstance(r.get("clv_pct"), (int, float))]

    total_picks = len(rows)
    settled_picks = len(settled)

    total_profit = round(sum(float(r.get("profit_units") or 0.0) for r in settled), 4)
    roi_pct = round((total_profit / settled_picks) * 100, 2) if settled_picks else 0.0
    hit_rate = round((sum(int(r["result"]) for r in settled) / settled_picks) * 100, 2) if settled_picks else 0.0

    avg_clv_pct = round(sum(float(r["clv_pct"]) for r in clv_rows) / len(clv_rows) * 100, 2) if clv_rows else 0.0
    positive_clv_rate = round(sum(1 for r in clv_rows if float(r["clv_pct"]) > 0) / len(clv_rows) * 100, 2) if clv_rows else 0.0

    per_market: dict[str, dict] = {}
    for row in settled:
        bucket = per_market.setdefault(
            row["market"],
            {"bets": 0, "profit_units": 0.0, "wins": 0},
        )
        bucket["bets"] += 1
        bucket["profit_units"] += float(row.get("profit_units") or 0.0)
        bucket["wins"] += int(row.get("result") or 0)

    for market, bucket in per_market.items():
        bets = bucket["bets"]
        bucket["profit_units"] = round(bucket["profit_units"], 4)
        bucket["roi_pct"] = round((bucket["profit_units"] / bets) * 100, 2) if bets else 0.0
        bucket["hit_rate"] = round((bucket["wins"] / bets) * 100, 2) if bets else 0.0

    return {
        "total_picks": total_picks,
        "settled_picks": settled_picks,
        "profit_units": total_profit,
        "roi_pct": roi_pct,
        "hit_rate_pct": hit_rate,
        "avg_clv_pct": avg_clv_pct,
        "positive_clv_rate_pct": positive_clv_rate,
        "per_market": per_market,
    }
