"""Filter DevEval data.

``data.jsonl`` → ``data_filtered.jsonl``
Keep only samples whose dependencies are non-empty.

Usage::

    python filter_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_JSONL = BASE_DIR / "DevEval" / "data.jsonl"
OUTPUT_PATH = BASE_DIR / "data_filtered.jsonl"


def main() -> None:
    kept = 0
    skipped = 0

    with open(DATA_JSONL, "r") as fin, open(OUTPUT_PATH, "w") as fout:
        for line in fin:
            sample = json.loads(line)
            dep = sample["dependency"]
            if dep.get("intra_class") or dep.get("intra_file") or dep.get("cross_file"):
                fout.write(line)
                kept += 1
            else:
                skipped += 1

    print(f"data.jsonl: total {kept + skipped}, kept {kept}, skipped {skipped}")
    print(f"  Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
