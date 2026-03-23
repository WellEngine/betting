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

from value_engine.roi.tracker import update_closing_lines


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Update tracker with closing odds")
    parser.add_argument("--closing", required=True, help="Path to closing odds JSON")
    args = parser.parse_args()

    closing_rows = json.loads(Path(args.closing).read_text(encoding="utf-8"))
    path = update_closing_lines(closing_rows)
    print(f"Updated tracker: {path}")


if __name__ == "__main__":
    main()
