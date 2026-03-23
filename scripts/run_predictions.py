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

from value_engine.engine_safe import find_safe_picks
from value_engine.engine_value import find_value_picks


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run value engine predictions")
    parser.add_argument("--fixtures", required=True, help="Path to fixtures JSON")
    parser.add_argument("--mode", choices=["value", "safe", "both"], default="both")
    parser.add_argument("--output", help="Optional output JSON path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))

    result: dict = {}
    if args.mode in {"value", "both"}:
        result["value"] = find_value_picks(fixtures, limit=args.limit)
    if args.mode in {"safe", "both"}:
        result["safe"] = find_safe_picks(fixtures, limit=args.limit)

    payload = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
        print(f"Saved to: {output_path}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
