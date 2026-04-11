"""Filter DevEval data and prompt files to keep only samples with dependencies.

Samples whose ``intra_class``, ``intra_file``, and ``cross_file`` are all
empty are identical to the without_context baseline, so they are excluded.

Produces:
* ``data_filtered.jsonl`` -- filtered metadata
* ``output/prompt_without_context.jsonl`` -- filtered without_context prompts
* ``output/prompt_local_infilling.jsonl`` -- filtered local_infilling prompts

Usage::

    python filter_data.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_JSONL = BASE_DIR / "DevEval" / "data.jsonl"
OUTPUT_PATH = BASE_DIR / "data_filtered.jsonl"

# DevEval baseline prompt files to filter.
PROMPT_SOURCES = {
    "without_context": (
        BASE_DIR / "DevEval" / "Experiments" / "prompt" / "without_context" / "gpt-4-1106_prompt.jsonl"
    ),
    "local_infilling": (
        BASE_DIR / "DevEval" / "Experiments" / "prompt" / "local_infilling" / "gpt-4-1106_prompt.jsonl"
    ),
}
OUTPUT_DIR = BASE_DIR / "output"


def main() -> None:
    # --- 1. Filter data.jsonl ---
    kept_ns: set[str] = set()
    kept = 0
    skipped = 0

    with open(DATA_JSONL, "r") as fin, open(OUTPUT_PATH, "w") as fout:
        for line in fin:
            sample = json.loads(line)
            dep = sample["dependency"]
            if dep.get("intra_class") or dep.get("intra_file") or dep.get("cross_file"):
                fout.write(line)
                kept += 1
                kept_ns.add(sample["namespace"])
            else:
                skipped += 1

    print(f"data.jsonl: total {kept + skipped}, kept {kept}, skipped {skipped}")
    print(f"  Saved to {OUTPUT_PATH}")

    # --- 2. Filter baseline prompt files ---
    OUTPUT_DIR.mkdir(exist_ok=True)

    for label, src_path in PROMPT_SOURCES.items():
        if not src_path.exists():
            print(f"\n{label}: source not found ({src_path}), skipping")
            continue

        out_path = OUTPUT_DIR / f"prompt_{label}.jsonl"
        total = 0
        written = 0

        with open(src_path, "r") as fin, open(out_path, "w") as fout:
            for line in fin:
                total += 1
                entry = json.loads(line)
                if entry["namespace"] in kept_ns:
                    fout.write(line)
                    written += 1

        print(f"\n{label}: {total} -> {written}")
        print(f"  Saved to {out_path}")


if __name__ == "__main__":
    main()
