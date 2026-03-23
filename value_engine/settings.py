from __future__ import annotations

import os
from pathlib import Path


def _as_bool(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


PROJECT_ROOT = Path(__file__).resolve().parents[1]

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
API_FOOTBALL_BASE_URL = os.getenv(
    "API_FOOTBALL_BASE_URL",
    "https://v3.football.api-sports.io",
).rstrip("/")

OFFLINE_DIR_RAW = os.getenv("VALUE_ENGINE_OFFLINE_DIR", "").strip()
OFFLINE_DIR = Path(OFFLINE_DIR_RAW).resolve() if OFFLINE_DIR_RAW else None

RUNTIME_DIR_RAW = os.getenv("VALUE_ENGINE_DATA_DIR", ".runtime").strip()
RUNTIME_DIR = Path(RUNTIME_DIR_RAW)
if not RUNTIME_DIR.is_absolute():
    RUNTIME_DIR = (PROJECT_ROOT / RUNTIME_DIR).resolve()
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

TRACKED_PICKS_FILE = RUNTIME_DIR / "tracked_picks.json"
CALIBRATION_FILE = RUNTIME_DIR / "calibration_models.json"

ENABLE_CALIBRATION = _as_bool(os.getenv("VALUE_ENGINE_ENABLE_CALIBRATION"), default=False)
ENABLE_PLAYER_IMPACT = _as_bool(os.getenv("VALUE_ENGINE_ENABLE_PLAYER_IMPACT"), default=False)
