"""Compare pass@1 results across the 3 core prompt variants.

A trimmed-down version of compare_results.py that only considers
without_context / sd_sd / full_full — useful for a concise paper table.

Loads log.jsonl from each variant's output directory and produces:
  - Terminal summary
  - Markdown report (output/analysis_core.md)
  - Per-sample detail (output/comparison_detail_core.jsonl)

Usage::

    python compare_results_core.py
    python compare_results_core.py --output_root output_full
    python compare_results_core.py --model gpt-5.4-mini
"""

from __future__ import annotations

import argparse

from compare_results import (
    SHORT,
    BASE_DIR,
    load_log,
    load_prompt_sizes,
    load_dep_info,
    generate_md,
)
import json
from pathlib import Path


CORE_VARIANTS = [
    "without_context",
    "func-sd_class-sd",
    "func-full_class-full",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare pass@1 across the 3 core variants",
    )
    parser.add_argument("--output_root", default="output")
    parser.add_argument("--model", default="gpt-5.4-mini")
    args = parser.parse_args()

    root = BASE_DIR / args.output_root
    gen_dir = root / "generated_code"

    all_results: dict[str, dict[str, bool]] = {}
    for variant in CORE_VARIANTS:
        log_path = gen_dir / args.model / variant / "log.jsonl"
        if not log_path.exists():
            print(f"  SKIP {variant}: {log_path} not found")
            continue
        all_results[variant] = load_log(log_path)
        print(f"  Loaded {variant}: {len(all_results[variant])} samples")

    if len(all_results) < 2:
        print("Need at least 2 variants to compare.")
        return

    variants = [v for v in CORE_VARIANTS if v in all_results]

    ns_sets = [set(r.keys()) for r in all_results.values()]
    common_ns = sorted(set.intersection(*ns_sets))
    print(f"  Common samples: {len(common_ns)}")

    prompt_sizes = load_prompt_sizes(root / "prompt", variants)
    dep_info = load_dep_info()

    md_path = root / "analysis_core.md"
    generate_md(
        variants, all_results, common_ns,
        prompt_sizes, dep_info, args.model, md_path,
    )
    print(f"\n  Report saved to {md_path}")

    detail_path = root / "comparison_detail_core.jsonl"
    sn = {v: SHORT.get(v, v) for v in variants}
    with open(detail_path, "w") as f:
        for ns in common_ns:
            entry = {"namespace": ns}
            for v in variants:
                entry[sn[v]] = "Pass" if all_results[v][ns] else "Fail"
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  Detail saved to {detail_path}")


if __name__ == "__main__":
    main()
