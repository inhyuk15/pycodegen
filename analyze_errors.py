"""Analyze pass@1 errors from log.jsonl files.

Reads stderr captured by pass_k_verbose.py and produces error summaries.

Usage::

    # Summarize errors for one variant
    python analyze_errors.py summary \
        --log_file output/generated_code/func-full_class-full/gpt-5.4-mini/log.jsonl

    # Summarize with markdown output
    python analyze_errors.py summary \
        --log_file output/generated_code/func-full_class-full/gpt-5.4-mini/log.jsonl \
        --md

    # Compare errors across variants
    python analyze_errors.py compare \
        --log_files output/generated_code/*/gpt-5.4-mini/log.jsonl
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path


def classify_error(stderr: str) -> str:
    """Classify error into a category based on stderr content."""
    if not stderr:
        return "unknown"
    s = stderr.lower()
    if "timed out" in s or "timeout" in s:
        return "timeout"
    if "syntaxerror" in s:
        return "syntax_error"
    if "indentationerror" in s:
        return "indentation_error"
    if "nameerror" in s:
        return "name_error"
    if "attributeerror" in s:
        return "attribute_error"
    if "typeerror" in s:
        return "type_error"
    if "importerror" in s or "modulenotfounderror" in s:
        return "import_error"
    if "keyerror" in s:
        return "key_error"
    if "indexerror" in s:
        return "index_error"
    if "valueerror" in s:
        return "value_error"
    if "assertionerror" in s or "assert" in s:
        return "assertion_error"
    if "recursionerror" in s:
        return "recursion_error"
    if "notimplementederror" in s:
        return "not_implemented"
    if "pass only" in s:
        return "empty_completion"
    if "failed" in s:
        return "test_failed"
    return "other"


def extract_error_line(stderr: str) -> str:
    """Extract the most relevant error line from stderr."""
    lines = stderr.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        if any(e in line for e in ["Error:", "Exception:", "FAILED", "assert"]):
            return line[:200]
    for line in reversed(lines):
        if line.strip():
            return line.strip()[:200]
    return ""


def load_failures(log_path: Path) -> list[dict]:
    """Load failed entries from log.jsonl."""
    failures = []
    with open(log_path) as f:
        for line in f:
            d = json.loads(line)
            if d.get("Result", "") != "Pass":
                stderr = d.get("stderr", "")
                failures.append({
                    "namespace": d["namespace"],
                    "result": d["Result"],
                    "category": classify_error(stderr),
                    "error_line": extract_error_line(stderr) if stderr else "",
                    "stderr": stderr,
                })
    return failures


def cmd_summary(args: argparse.Namespace) -> None:
    """Summarize error categories."""
    failures = load_failures(args.log_file)
    if not failures:
        print("No failures found.")
        return

    total = len(failures)
    categories = Counter(f["category"] for f in failures)

    # Check if stderr is present
    has_stderr = sum(1 for f in failures if f["stderr"])
    if has_stderr == 0:
        print("Warning: no stderr in log.jsonl. Run pass_k_verbose.py instead of pass_k.py.")
        print()

    print(f"\n{'Category':<25s} {'Count':>6s} {'%':>6s}")
    print("-" * 40)
    for cat, count in categories.most_common():
        print(f"{cat:<25s} {count:>6d} {count/total*100:>5.1f}%")
    print("-" * 40)
    print(f"{'Total':<25s} {total:>6d}")

    if not args.brief:
        by_cat = defaultdict(list)
        for f in failures:
            by_cat[f["category"]].append(f)

        print("\n\nExamples per category:")
        for cat, count in categories.most_common(10):
            print(f"\n### {cat} ({count})")
            for f in by_cat[cat][:3]:
                print(f"  {f['namespace']}")
                if f["error_line"]:
                    print(f"    {f['error_line'][:120]}")

    if args.md:
        lines = [f"# Error Analysis ({total} failures)", ""]
        lines.append("| Category | Count | % |")
        lines.append("|----------|------:|----:|")
        for cat, count in categories.most_common():
            lines.append(f"| {cat} | {count} | {count/total*100:.1f}% |")
        lines.append("")

        by_cat = defaultdict(list)
        for f in failures:
            by_cat[f["category"]].append(f)

        lines.append("## Examples")
        lines.append("")
        for cat, count in categories.most_common(10):
            lines.append(f"### {cat} ({count})")
            lines.append("")
            lines.append("| Namespace | Error |")
            lines.append("|-----------|-------|")
            for f in by_cat[cat][:5]:
                err = f["error_line"][:100].replace("|", "\\|")
                lines.append(f"| {f['namespace']} | {err} |")
            lines.append("")

        md_path = args.log_file.parent / "errors.md"
        with open(md_path, "w") as f:
            f.write("\n".join(lines))
        print(f"\nMarkdown saved to {md_path}")


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare error categories across variants."""
    files = []
    for pattern in args.log_files:
        files.extend(glob.glob(pattern))

    if not files:
        print("No log files found.")
        return

    all_data = {}
    for fpath in sorted(files):
        parts = Path(fpath).parts
        variant = parts[-3] if len(parts) >= 3 else fpath
        failures = load_failures(Path(fpath))
        all_data[variant] = Counter(f["category"] for f in failures)

    all_cats = sorted(set().union(*(c.keys() for c in all_data.values())))
    variants = list(all_data.keys())

    header = f"{'Category':<25s}" + "".join(f" {v:>15s}" for v in variants)
    print(header)
    print("-" * len(header))
    for cat in all_cats:
        row = f"{cat:<25s}"
        for v in variants:
            row += f" {all_data[v].get(cat, 0):>15d}"
        print(row)
    print("-" * len(header))
    totals = f"{'TOTAL':<25s}"
    for v in variants:
        totals += f" {sum(all_data[v].values()):>15d}"
    print(totals)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze pass@1 errors")
    sub = parser.add_subparsers(dest="command", required=True)

    p_summary = sub.add_parser("summary", help="Summarize errors from log.jsonl")
    p_summary.add_argument("--log_file", type=Path, required=True)
    p_summary.add_argument("--brief", action="store_true")
    p_summary.add_argument("--md", action="store_true", help="Save markdown summary")

    p_compare = sub.add_parser("compare", help="Compare errors across variants")
    p_compare.add_argument("--log_files", nargs="+", required=True)

    args = parser.parse_args()
    if args.command == "summary":
        cmd_summary(args)
    elif args.command == "compare":
        cmd_compare(args)


if __name__ == "__main__":
    main()
