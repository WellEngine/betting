from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from value_engine.roi.tracker import settle_picks


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Settle tracked picks using results JSON")
    parser.add_argument("--results", required=True, help="Path to results JSON")
    args = parser.parse_args()

    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    path = settle_picks(results)
    print(f"Updated tracker: {path}")


if __name__ == "__main__":
    main()
