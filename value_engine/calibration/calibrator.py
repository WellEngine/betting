from __future__ import annotations

import json
import math
from bisect import bisect_right
from pathlib import Path
from typing import Dict, Iterable, List

from value_engine.settings import CALIBRATION_FILE


def _identity_model(market: str) -> Dict:
    return {
        "market": market,
        "points": [[0.0, 0.0], [1.0, 1.0]],
        "metadata": {"status": "identity"},
    }


def load_calibration_models(path: Path | None = None) -> Dict[str, Dict]:
    path = path or CALIBRATION_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_calibration_models(models: Dict[str, Dict], path: Path | None = None) -> Path:
    path = path or CALIBRATION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _extract_raw_probability(row: dict) -> float:
    for key in ("raw_probability", "probability_raw", "model_probability_raw", "probability"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def _extract_outcome(row: dict) -> int | None:
    value = row.get("result")
    if value is None:
        return None
    return int(value)


def _piecewise_linear(points: List[List[float]], x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    xs = [p[0] for p in points]
    pos = bisect_right(xs, x)

    if pos <= 0:
        return points[0][1]
    if pos >= len(points):
        return points[-1][1]

    x0, y0 = points[pos - 1]
    x1, y1 = points[pos]

    if abs(x1 - x0) < 1e-9:
        return y1

    ratio = (x - x0) / (x1 - x0)
    return y0 + ratio * (y1 - y0)


def calibrate_probability(market: str, raw_probability: float, models: Dict[str, Dict] | None = None) -> float:
    models = models or load_calibration_models()
    model = models.get(market)
    if not model:
        return round(min(max(raw_probability, 0.0), 1.0), 4)

    points = model.get("points") or [[0.0, 0.0], [1.0, 1.0]]
    calibrated = _piecewise_linear(points, raw_probability)
    return round(min(max(calibrated, 0.0), 1.0), 4)


def fit_calibration_models(
    rows: Iterable[dict],
    *,
    n_bins: int = 8,
    min_samples: int = 30,
    smoothing: float = 8.0,
) -> Dict[str, Dict]:
    rows = list(rows)
    markets = sorted({row.get("market") for row in rows if row.get("market")})
    models: Dict[str, Dict] = {}

    for market in markets:
        market_rows = []
        for row in rows:
            if row.get("market") != market:
                continue
            outcome = _extract_outcome(row)
            if outcome is None:
                continue
            market_rows.append(
                {
                    "raw_probability": min(max(_extract_raw_probability(row), 0.0), 1.0),
                    "result": outcome,
                }
            )

        if len(market_rows) < min_samples:
            models[market] = {
                **_identity_model(market),
                "metadata": {
                    "status": "not_enough_samples",
                    "samples": len(market_rows),
                    "min_samples": min_samples,
                },
            }
            continue

        market_rows.sort(key=lambda item: item["raw_probability"])
        global_rate = sum(r["result"] for r in market_rows) / len(market_rows)
        bin_size = math.ceil(len(market_rows) / n_bins)

        points: List[List[float]] = [[0.0, 0.0]]
        for start in range(0, len(market_rows), bin_size):
            chunk = market_rows[start:start + bin_size]
            if not chunk:
                continue
            mean_pred = sum(r["raw_probability"] for r in chunk) / len(chunk)
            observed = sum(r["result"] for r in chunk) / len(chunk)
            observed_smoothed = ((observed * len(chunk)) + (global_rate * smoothing)) / (len(chunk) + smoothing)
            points.append([round(mean_pred, 4), round(observed_smoothed, 4)])

        points.append([1.0, 1.0])

        deduped: List[List[float]] = []
        for x, y in sorted(points, key=lambda item: item[0]):
            if deduped and abs(deduped[-1][0] - x) < 1e-9:
                deduped[-1][1] = round((deduped[-1][1] + y) / 2, 4)
            else:
                deduped.append([x, y])

        models[market] = {
            "market": market,
            "points": deduped,
            "metadata": {
                "status": "trained",
                "samples": len(market_rows),
                "bins": n_bins,
                "smoothing": smoothing,
                "global_rate": round(global_rate, 4),
            },
        }

    return models
