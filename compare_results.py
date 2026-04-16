"""Compare pass@1 results across prompt variants.

Loads log.jsonl from each variant's output directory and produces:
  - Terminal summary
  - Markdown report (output/analysis.md)
  - Per-sample detail (output/comparison_detail.jsonl)

Usage::

    python compare_results.py                            # 1323 samples (output/)
    python compare_results.py --output_root output_full  # 1825 samples
    python compare_results.py --model gpt-5.4-mini
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).parent

VARIANT_ORDER = [
    "without_context",
    "func-sd_class-sd",
    "func-full_class-full",
]

SHORT = {
    "without_context": "without",
    "local_infilling": "local",
    "func-sd_class-sd": "sd_sd",
    "func-full_class-full": "full_full",
}


def load_log(log_path: Path) -> dict[str, bool]:
    results = {}
    with open(log_path) as f:
        for line in f:
            d = json.loads(line)
            results[d["namespace"]] = d["Result"] == "Pass"
    return results


def load_prompt_sizes(prompt_dir: Path, variants: list[str]) -> dict[str, dict[str, int]]:
    """Load prompt sizes per namespace per variant."""
    sizes: dict[str, dict[str, int]] = defaultdict(dict)
    for v in variants:
        path = prompt_dir / f"prompt_{v}.jsonl"
        if not path.exists():
            continue
        with open(path) as f:
            for line in f:
                d = json.loads(line)
                sizes[d["namespace"]][v] = len(d["prompt"])
    return dict(sizes)


def load_dep_info() -> dict[str, dict]:
    """Load dependency info from data_filtered.jsonl."""
    deps = {}
    path = BASE_DIR / "data_filtered.jsonl"
    if not path.exists():
        return deps
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            dep = d["dependency"]
            deps[d["namespace"]] = {
                "intra_class": len(dep.get("intra_class", [])),
                "intra_file": len(dep.get("intra_file", [])),
                "cross_file": len(dep.get("cross_file", [])),
                "total": (
                    len(dep.get("intra_class", []))
                    + len(dep.get("intra_file", []))
                    + len(dep.get("cross_file", []))
                ),
            }
    return deps


def repo_name(ns: str) -> str:
    """Extract repo name from namespace (first component)."""
    return ns.split(".")[0]


def generate_md(
    variants: list[str],
    results: dict[str, dict[str, bool]],
    common_ns: list[str],
    prompt_sizes: dict[str, dict[str, int]],
    dep_info: dict[str, dict],
    model: str,
    output_path: Path,
) -> str:
    lines: list[str] = []
    sn = {v: SHORT.get(v, v) for v in variants}

    lines.append(f"# pass@1 Analysis ({model}, {len(common_ns)} samples)")
    lines.append("")

    # --- 1. Overall ---
    lines.append("## 1. Overall pass@1")
    lines.append("")
    lines.append("| Variant | Pass | Total | Rate |")
    lines.append("|---------|-----:|------:|-----:|")
    for v in variants:
        passed = sum(1 for ns in common_ns if results[v][ns])
        lines.append(f"| {sn[v]} | {passed} | {len(common_ns)} | {passed/len(common_ns)*100:.1f}% |")
    lines.append("")

    # --- 2. Monotonicity check ---
    lines.append("## 2. Context monotonicity (more context should help)")
    lines.append("")
    lines.append("Expected order: without < sd_sd < full_full")
    lines.append("")

    pairs = []
    for i in range(len(variants) - 1):
        pairs.append((variants[i], variants[i + 1]))
    # Also add without vs full_full
    if len(variants) >= 3:
        pairs.append((variants[0], variants[-1]))

    lines.append("| Comparison | Both pass | A only (violation) | B only (improvement) | Both fail |")
    lines.append("|------------|----------:|-------------------:|---------------------:|----------:|")
    for v1, v2 in pairs:
        both = sum(1 for ns in common_ns if results[v1][ns] and results[v2][ns])
        v1_only = sum(1 for ns in common_ns if results[v1][ns] and not results[v2][ns])
        v2_only = sum(1 for ns in common_ns if not results[v1][ns] and results[v2][ns])
        neither = sum(1 for ns in common_ns if not results[v1][ns] and not results[v2][ns])
        lines.append(
            f"| {sn[v1]} → {sn[v2]} | {both} | {v1_only} | {v2_only} | {neither} |"
        )
    lines.append("")

    # --- 3. Violations: without passed but others failed ---
    lines.append("## 3. Monotonicity violations")
    lines.append("")

    for v1, v2 in pairs:
        violations = [
            ns for ns in common_ns if results[v1][ns] and not results[v2][ns]
        ]
        if not violations:
            continue
        lines.append(f"### {sn[v1]} Pass → {sn[v2]} Fail ({len(violations)} cases)")
        lines.append("")
        lines.append("| Namespace | Deps | Prompt size ({}) | Prompt size ({}) | Ratio |".format(
            sn[v1], sn[v2]
        ))
        lines.append("|-----------|-----:|-----------------:|-----------------:|------:|")
        for ns in sorted(violations):
            dep_total = dep_info.get(ns, {}).get("total", "-")
            sz1 = prompt_sizes.get(ns, {}).get(v1, 0)
            sz2 = prompt_sizes.get(ns, {}).get(v2, 0)
            ratio = f"{sz2/sz1:.1f}x" if sz1 > 0 else "-"
            lines.append(f"| {ns} | {dep_total} | {sz1} | {sz2} | {ratio} |")
        lines.append("")

    # --- 4. sd_sd vs full_full deep dive ---
    if "func-sd_class-sd" in variants and "func-full_class-full" in variants:
        lines.append("## 4. sd_sd vs full_full")
        lines.append("")

        sd_only = [ns for ns in common_ns
                    if results["func-sd_class-sd"][ns] and not results["func-full_class-full"][ns]]
        full_only = [ns for ns in common_ns
                     if not results["func-sd_class-sd"][ns] and results["func-full_class-full"][ns]]

        lines.append(f"- sd_sd only pass: **{len(sd_only)}** (context noise)")
        lines.append(f"- full_full only pass: **{len(full_only)}** (more context helped)")
        lines.append(f"- Net gain from full: **+{len(full_only) - len(sd_only)}**")
        lines.append("")

        # Prompt size ratio distribution for sd_only
        if sd_only:
            ratios = []
            for ns in sd_only:
                sz_sd = prompt_sizes.get(ns, {}).get("func-sd_class-sd", 0)
                sz_full = prompt_sizes.get(ns, {}).get("func-full_class-full", 0)
                if sz_sd > 0:
                    ratios.append(sz_full / sz_sd)

            if ratios:
                lines.append("#### Prompt size ratio (full/sd) for sd-only wins:")
                lines.append("")
                bins = [
                    ("1.0x (identical)", lambda r: r <= 1.05),
                    ("1.1x ~ 1.5x", lambda r: 1.05 < r <= 1.5),
                    ("1.5x ~ 2.0x", lambda r: 1.5 < r <= 2.0),
                    ("2.0x ~ 3.0x", lambda r: 2.0 < r <= 3.0),
                    ("3.0x+", lambda r: r > 3.0),
                ]
                lines.append("| Range | Count |")
                lines.append("|-------|------:|")
                for label, pred in bins:
                    lines.append(f"| {label} | {sum(1 for r in ratios if pred(r))} |")
                lines.append(f"| **Average** | **{sum(ratios)/len(ratios):.1f}x** |")
                lines.append("")

    # --- 5. Pass/fail pattern distribution ---
    lines.append("## 5. Pass/fail patterns")
    lines.append("")
    patterns: Counter[tuple[str, ...]] = Counter()
    for ns in common_ns:
        pattern = tuple("P" if results[v][ns] else "F" for v in variants)
        patterns[pattern] += 1

    header = " | ".join(sn[v] for v in variants)
    lines.append(f"| {header} | Count | % |")
    lines.append("|" + "|".join(["------"] * len(variants)) + "|------:|----:|")
    for pattern, count in patterns.most_common():
        row = " | ".join(pattern)
        pct = count / len(common_ns) * 100
        lines.append(f"| {row} | {count} | {pct:.1f}% |")
    lines.append("")

    # --- 6. Per-repo pass rates ---
    lines.append("## 6. Per-repo pass rates (repos with 5+ samples)")
    lines.append("")

    repo_stats: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for ns in common_ns:
        repo = repo_name(ns)
        for v in variants:
            repo_stats[repo][v].append(results[v][ns])

    # Sort by sample count desc
    sorted_repos = sorted(repo_stats.items(), key=lambda x: len(list(x[1].values())[0]), reverse=True)

    header = " | ".join(f"{sn[v]}" for v in variants)
    lines.append(f"| Repo | Samples | {header} |")
    lines.append("|------|--------:|" + "|".join(["------:"] * len(variants)) + "|")
    for repo, stats in sorted_repos:
        n = len(stats[variants[0]])
        if n < 5:
            continue
        rates = []
        for v in variants:
            passed = sum(stats[v])
            rates.append(f"{passed/n*100:.0f}%")
        lines.append(f"| {repo} | {n} | {' | '.join(rates)} |")
    lines.append("")

    md_text = "\n".join(lines)
    with open(output_path, "w") as f:
        f.write(md_text)
    return md_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare pass@1 across variants")
    parser.add_argument("--output_root", default="output")
    parser.add_argument("--model", default="gpt-5.4-mini")
    parser.add_argument(
        "--variants", nargs="+", default=VARIANT_ORDER,
    )
    args = parser.parse_args()

    root = BASE_DIR / args.output_root
    gen_dir = root / "generated_code"

    # Load results
    all_results: dict[str, dict[str, bool]] = {}
    for variant in args.variants:
        log_path = gen_dir / variant / args.model / "log.jsonl"
        if not log_path.exists():
            print(f"  SKIP {variant}: {log_path} not found")
            continue
        all_results[variant] = load_log(log_path)
        print(f"  Loaded {variant}: {len(all_results[variant])} samples")

    if len(all_results) < 2:
        print("Need at least 2 variants to compare.")
        return

    variants = [v for v in args.variants if v in all_results]

    # Common namespaces
    ns_sets = [set(r.keys()) for r in all_results.values()]
    common_ns = sorted(set.intersection(*ns_sets))
    print(f"  Common samples: {len(common_ns)}")

    # Load extra data
    prompt_sizes = load_prompt_sizes(root / "prompt", variants)
    dep_info = load_dep_info()

    # Generate markdown report
    md_path = root / "analysis.md"
    md_text = generate_md(
        variants, all_results, common_ns,
        prompt_sizes, dep_info, args.model, md_path,
    )
    print(f"\n  Report saved to {md_path}")

    # Save per-sample detail
    detail_path = root / "comparison_detail.jsonl"
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
