"""Build a per-sample variant result matrix and categorize interesting cases.

Output:
  - output/sample_matrix.jsonl — one line per namespace with:
        { namespace, deps:{intra_class,intra_file,cross_file,total},
          func_name, is_method, class_name,
          results:{variant: "P"|"F"},
          category: <label> }
  - output/category_summary.md — category counts + example namespaces

Categories (priority order):
  - all_pass                — trivial
  - all_fail                — nothing helps
  - local_only              — only local_infilling passes (AST missed intra-file deps)
  - sd_wins_over_full       — sd_sd Pass but full_full Fail (H1: less is more)
  - needs_class_full        — sd_sd Fail but sd_full/full_full Pass (class body required)
  - needs_func_full         — sd_full Fail but full_full Pass (function body required)
  - sd_init_unlock          — sd_init Pass but sd_sd Fail (shallow __init__ enough)
  - mixed                   — no clean pattern
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent
MODEL = "gpt-5.4-mini"
GEN_DIR = BASE / "output" / "generated_code" / MODEL

VARIANTS = [
    "without_context",
    "local_infilling",
    "func-sd_class-sd",
    "func-sd_class-sd_init",
    "func-full_class-sd",
    "func-sd_class-full",
    "func-full_class-full",
]

SHORT = {
    "without_context": "without",
    "local_infilling": "local",
    "func-sd_class-sd": "sd_sd",
    "func-sd_class-sd_init": "sd_init",
    "func-full_class-sd": "full_sd",
    "func-sd_class-full": "sd_full",
    "func-full_class-full": "full_full",
}


def load_logs() -> dict[str, dict[str, bool]]:
    """Return {namespace: {short_variant: passed_bool}}."""
    data: dict[str, dict[str, bool]] = {}
    for v in VARIANTS:
        path = GEN_DIR / v / "log.jsonl"
        if not path.exists():
            print(f"[skip] {v}: {path} not found")
            continue
        with open(path) as f:
            for line in f:
                d = json.loads(line)
                data.setdefault(d["namespace"], {})[SHORT[v]] = (d["Result"] == "Pass")
    return data


def load_deps() -> dict[str, dict]:
    deps: dict[str, dict] = {}
    with open(BASE / "data_filtered.jsonl") as f:
        for line in f:
            d = json.loads(line)
            dep = d.get("dependency", {})
            deps[d["namespace"]] = {
                "intra_class": len(dep.get("intra_class", [])),
                "intra_file": len(dep.get("intra_file", [])),
                "cross_file": len(dep.get("cross_file", [])),
                "total": (
                    len(dep.get("intra_class", []))
                    + len(dep.get("intra_file", []))
                    + len(dep.get("cross_file", []))
                ),
                "type": d.get("type", "function"),
            }
    return deps


def parse_namespace(ns: str, is_method: bool) -> tuple[str, str]:
    """Return (class_name_or_empty, function_name)."""
    parts = ns.split(".")
    fname = parts[-1]
    class_name = parts[-2] if is_method else ""
    return class_name, fname


def categorize(r: dict[str, bool]) -> str:
    """Single label per sample. Earlier branches take priority."""
    # Require at least these variants to exist.
    required = ("without", "local", "sd_sd", "sd_full", "full_full")
    if not all(k in r for k in required):
        return "missing_variants"

    passed = [k for k, v in r.items() if v]
    if not passed:
        return "all_fail"
    if len(passed) == len(r):
        return "all_pass"

    # Local-only wins (our AST variants can't recover intra-file context)
    ast_keys = [k for k in ("sd_sd", "sd_init", "full_sd", "sd_full", "full_full") if k in r]
    if r["local"] and not any(r[k] for k in ast_keys):
        return "local_only"

    # sd wins, full loses → less context was better
    if r["sd_sd"] and not r["full_full"]:
        return "sd_wins_over_full"

    # sd_sd fails but class-full unlocks
    if not r["sd_sd"] and r.get("sd_full", False) and not r.get("full_sd", True):
        return "needs_class_full"

    # sd_full fails but full_full passes → function body helped
    if r.get("sd_full") is False and r["full_full"]:
        return "needs_func_full"

    # sd_init unlocks where sd_sd fails
    if not r["sd_sd"] and r.get("sd_init", False):
        return "sd_init_unlock"

    return "mixed"


def main() -> None:
    results = load_logs()
    deps = load_deps()

    # Build per-sample records
    records = []
    cat_counts: Counter[str] = Counter()
    for ns, r in results.items():
        dep = deps.get(ns, {})
        is_method = dep.get("type") == "method"
        class_name, fname = parse_namespace(ns, is_method)
        cat = categorize(r)
        cat_counts[cat] += 1
        records.append({
            "namespace": ns,
            "class_name": class_name,
            "func_name": fname,
            "is_method": is_method,
            "deps": {
                "intra_class": dep.get("intra_class", 0),
                "intra_file": dep.get("intra_file", 0),
                "cross_file": dep.get("cross_file", 0),
                "total": dep.get("total", 0),
            },
            "results": {k: ("P" if v else "F") for k, v in r.items()},
            "category": cat,
        })

    # Save matrix
    out_path = BASE / "output" / "sample_matrix.jsonl"
    with open(out_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} records to {out_path}")

    # Category summary
    lines = [f"# Category summary ({MODEL}, {len(records)} samples)\n"]
    lines.append("| Category | Count | % |")
    lines.append("|----------|------:|----:|")
    total = len(records)
    for cat, n in cat_counts.most_common():
        lines.append(f"| {cat} | {n} | {n/total*100:.1f}% |")
    lines.append("")

    # Interesting categories: show 5 example namespaces each
    lines.append("## Examples per category")
    for cat in ("local_only", "sd_wins_over_full", "needs_class_full",
                "needs_func_full", "sd_init_unlock", "mixed"):
        examples = [r for r in records if r["category"] == cat][:10]
        if not examples:
            continue
        lines.append(f"\n### {cat} (n={cat_counts[cat]})")
        lines.append("")
        lines.append("| namespace | method? | intra_class | intra_file | cross_file | results |")
        lines.append("|-----------|:-------:|:-----------:|:----------:|:----------:|---------|")
        for r in examples:
            d = r["deps"]
            method_mark = "M" if r["is_method"] else "f"
            pattern = " ".join(f"{k}={r['results'].get(k,'-')}" for k in (
                "without", "sd_sd", "sd_init", "full_sd", "sd_full", "full_full", "local"
            ))
            lines.append(f"| {r['namespace']} | {method_mark} | {d['intra_class']} | {d['intra_file']} | {d['cross_file']} | {pattern} |")

    md_path = BASE / "output" / "category_summary.md"
    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Wrote category summary to {md_path}")

    print("\n=== Category counts ===")
    for cat, n in cat_counts.most_common():
        print(f"  {cat:30s} {n:>5}")


if __name__ == "__main__":
    main()
