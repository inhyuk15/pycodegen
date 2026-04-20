"""Split samples by pass/fail pattern across variants.

Reads log.jsonl from each variant and groups samples by their
pass/fail pattern. Saves each group as a separate JSONL file
with full sample info from DevEval data.jsonl.

Usage::

    python split_patterns.py
    python split_patterns.py --output_root output_full --model gpt-5.4-mini
    python split_patterns.py --variants without_context func-sd_class-sd func-full_class-full
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent

SHORT = {
    "without_context": "without",
    "local_infilling": "local",
    "func-sd_class-sd": "sd_sd",
    "func-full_class-full": "full_full",
}


def load_log(path: Path) -> dict[str, bool]:
    results = {}
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            results[d["namespace"]] = d["Result"] == "Pass"
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Split samples by pass/fail pattern")
    parser.add_argument("--output_root", default="output")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument("--data_file", default="DevEval/data.jsonl")
    parser.add_argument(
        "--variants", nargs="+",
        default=["without_context", "func-sd_class-sd", "func-full_class-full"],
    )
    args = parser.parse_args()

    root = BASE_DIR / args.output_root
    gen_dir = root / "generated_code"

    # Load results
    all_results = {}
    for v in args.variants:
        log_path = gen_dir / v / args.model / "log.jsonl"
        if not log_path.exists():
            print(f"  SKIP {v}: {log_path} not found")
            continue
        all_results[v] = load_log(log_path)
        print(f"  Loaded {v}: {len(all_results[v])} samples")

    variants = [v for v in args.variants if v in all_results]
    sn = {v: SHORT.get(v, v) for v in variants}

    # Common namespaces
    ns_sets = [set(r.keys()) for r in all_results.values()]
    common_ns = sorted(set.intersection(*ns_sets))
    print(f"  Common: {len(common_ns)}")

    # Load full sample data
    data = {}
    with open(BASE_DIR / args.data_file) as f:
        for line in f:
            d = json.loads(line)
            data[d["namespace"]] = d

    # Group by pattern
    groups: dict[str, list[str]] = defaultdict(list)
    for ns in common_ns:
        pattern = "_".join("P" if all_results[v][ns] else "F" for v in variants)
        groups[pattern] += [ns]

    # Save
    out_dir = root / "patterns"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pattern name with variant labels for clarity
    label = "_".join(sn[v] for v in variants)

    for pattern, ns_list in sorted(groups.items(), key=lambda x: -len(x[1])):
        filename = f"{pattern}.jsonl"
        path = out_dir / filename
        with open(path, "w") as f:
            for ns in ns_list:
                if ns in data:
                    f.write(json.dumps(data[ns], ensure_ascii=False) + "\n")
        print(f"  {pattern}: {len(ns_list):>4d} samples → {path}")

    # Save legend
    legend_path = out_dir / "README.txt"
    with open(legend_path, "w") as f:
        f.write(f"Pattern format: {'_'.join(sn[v] for v in variants)}\n")
        f.write(f"P = Pass, F = Fail\n\n")
        for i, v in enumerate(variants):
            f.write(f"  Position {i+1}: {sn[v]} ({v})\n")
        f.write(f"\nExample: F_P_P.jsonl = {sn[variants[0]]}=Fail, {sn[variants[1]]}=Pass, {sn[variants[2]]}=Pass\n")
    print(f"\n  Legend → {legend_path}")


if __name__ == "__main__":
    main()
