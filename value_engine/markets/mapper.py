from __future__ import annotations

from typing import Any, Dict


def map_market(
    *,
    market: str,
    probability: float,
    odds: float,
    value: float,
    confidence: float,
    source: str,
    raw_probability: float | None = None,
    fair_odds: float | None = None,
    edge: float | None = None,
    edge_percent: float | None = None,
    calibration_applied: bool = False,
) -> Dict[str, Any]:
    return {
        "market": market,
        "probability": round(probability, 4),
        "raw_probability": round(raw_probability if raw_probability is not None else probability, 4),
        "odds": round(float(odds), 3),
        "fair_odds": round(float(fair_odds), 3) if fair_odds is not None else None,
        "edge": round(float(edge), 4) if edge is not None else None,
        "edge_percent": round(float(edge_percent), 4) if edge_percent is not None else None,
        "value": round(float(value), 4),
        "confidence": round(float(confidence), 3),
        "source": source,
        "calibration_applied": calibration_applied,
    }
