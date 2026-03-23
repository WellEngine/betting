from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json

from dotenv import load_dotenv

from value_engine.calibration.calibrator import fit_calibration_models, save_calibration_models
from value_engine.roi.tracker import load_tracked_picks


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Fit calibration models from settled picks")
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--min-samples", type=int, default=30)
    parser.add_argument("--smoothing", type=float, default=8.0)
    args = parser.parse_args()

    rows = load_tracked_picks()
    models = fit_calibration_models(
        rows,
        n_bins=args.bins,
        min_samples=args.min_samples,
        smoothing=args.smoothing,
    )
    path = save_calibration_models(models)
    print(json.dumps({"saved_to": str(path), "markets": list(models)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
