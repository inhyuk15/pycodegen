"""Filter DevEval data and baseline prompt files.

Two-stage filtering:

1. ``data.jsonl`` → ``data_filtered.jsonl``
   Keep only samples whose dependencies are non-empty.

2. After ``build_prompt.py`` produces ``output/valid_namespaces.txt``,
   filter baseline prompt files (without_context, local_infilling) to the
   same namespace set so that all experiments are evaluated on identical
   samples.

Usage::

    python filter_data.py            # stage 1: filter data.jsonl
    python build_prompt.py           # produces valid_namespaces.txt
    python filter_data.py --stage2   # stage 2: filter baseline prompts
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_JSONL = BASE_DIR / "DevEval" / "data.jsonl"
OUTPUT_PATH = BASE_DIR / "data_filtered.jsonl"
OUTPUT_DIR = BASE_DIR / "output"
VALID_NS_PATH = OUTPUT_DIR / "valid_namespaces.txt"

PROMPT_SOURCES = {
    "without_context": (
        BASE_DIR / "DevEval" / "Experiments" / "prompt" / "without_context" / "gpt-4-1106_prompt.jsonl"
    ),
    "local_infilling": (
        BASE_DIR / "DevEval" / "Experiments" / "prompt" / "local_infilling" / "gpt-4-1106_prompt.jsonl"
    ),
}


def stage1() -> None:
    """Filter data.jsonl → data_filtered.jsonl (samples with dependencies)."""
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

    print(f"[stage1] data.jsonl: total {kept + skipped}, kept {kept}, skipped {skipped}")
    print(f"  Saved to {OUTPUT_PATH}")


def stage2() -> None:
    """Filter baseline prompts to valid_namespaces.txt."""
    if not VALID_NS_PATH.exists():
        print(f"[stage2] {VALID_NS_PATH} not found. Run build_prompt.py first.")
        return

    valid_ns: set[str] = set()
    with open(VALID_NS_PATH) as f:
        for line in f:
            valid_ns.add(line.strip())
    print(f"[stage2] Valid namespaces: {len(valid_ns)}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    for label, src_path in PROMPT_SOURCES.items():
        if not src_path.exists():
            print(f"\n  {label}: source not found ({src_path}), skipping")
            continue

        out_path = OUTPUT_DIR / f"prompt_{label}.jsonl"
        total = 0
        written = 0

        with open(src_path, "r") as fin, open(out_path, "w") as fout:
            for line in fin:
                total += 1
                entry = json.loads(line)
                if entry["namespace"] in valid_ns:
                    fout.write(line)
                    written += 1

        print(f"  {label}: {total} -> {written}, saved to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage2", action="store_true",
                        help="Run stage 2: filter baseline prompts using valid_namespaces.txt")
    args = parser.parse_args()

    if args.stage2:
        stage2()
    else:
        stage1()


if __name__ == "__main__":
    main()
