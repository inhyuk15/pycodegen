"""Extract the 1323-sample subset (with-deps) from 1825-sample output.

Given a completion.jsonl (or log.jsonl) that contains all 1825 DevEval
samples, write a filtered version with only the 1323 namespaces listed
in ``data_filtered.jsonl``. Useful when you want to generate once on
all 1825 (to compare to DevEval's full-set numbers) and reuse the same
outputs for our 1323-subset analysis.

Usage::

    # Extract 1323 completion from 1825 completion
    python extract_subset.py \\
        --input output_full/generated_code/{MODEL}/{VARIANT}/completion.jsonl \\
        --output output/generated_code/{MODEL}/{VARIANT}/completion.jsonl

    # Both completion and log at once (uses default filenames)
    python extract_subset.py \\
        --input_dir output_full/generated_code/{MODEL}/{VARIANT} \\
        --output_dir output/generated_code/{MODEL}/{VARIANT}

    # Custom filter file
    python extract_subset.py --input X.jsonl --output Y.jsonl --filter custom.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent


def load_valid_namespaces(filter_path: Path) -> set[str]:
    valid = set()
    with open(filter_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            valid.add(json.loads(line)["namespace"])
    return valid


def filter_jsonl(input_path: Path, output_path: Path, valid: set[str]) -> tuple[int, int]:
    """Copy lines whose ``namespace`` is in *valid*. Returns (kept, total)."""
    os.makedirs(output_path.parent, exist_ok=True)
    kept = total = 0
    with open(input_path) as fin, open(output_path, "w") as fout:
        for line in fin:
            total += 1
            try:
                ns = json.loads(line)["namespace"]
            except Exception:
                continue
            if ns in valid:
                fout.write(line)
                kept += 1
    return kept, total


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract 1323-sample subset from 1825 output")
    parser.add_argument("--input", type=Path, help="Single input file (e.g., completion.jsonl)")
    parser.add_argument("--output", type=Path, help="Single output file")
    parser.add_argument("--input_dir", type=Path, help="Dir with completion.jsonl (+ optional log.jsonl)")
    parser.add_argument("--output_dir", type=Path, help="Target dir to write filtered files")
    parser.add_argument("--filter", type=Path, default=BASE_DIR / "data_filtered.jsonl",
                        help="JSONL listing valid namespaces (default: data_filtered.jsonl)")
    args = parser.parse_args()

    if not args.filter.exists():
        raise SystemExit(f"Filter file not found: {args.filter}")

    valid = load_valid_namespaces(args.filter)
    print(f"[filter] {len(valid)} valid namespaces from {args.filter.name}")

    # Mode 1: single file
    if args.input and args.output:
        kept, total = filter_jsonl(args.input, args.output, valid)
        print(f"[ok] {args.input} → {args.output}  ({kept}/{total})")
        return

    # Mode 2: directory
    if args.input_dir and args.output_dir:
        for name in ("completion.jsonl", "log.jsonl"):
            src = args.input_dir / name
            dst = args.output_dir / name
            if not src.exists():
                print(f"[skip] {name}: not in {args.input_dir}")
                continue
            kept, total = filter_jsonl(src, dst, valid)
            print(f"[ok] {src} → {dst}  ({kept}/{total})")
        return

    parser.error("Provide either --input/--output or --input_dir/--output_dir")


if __name__ == "__main__":
    main()
