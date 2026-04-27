"""Build dependency-aware prompts for the DevEval benchmark.

Reads DevEval's ``data.jsonl``, uses AST extraction (from ast_extractor.py) to get
dependency source code, and injects it as context into the prompt file.

Usage::

    python build_prompt.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ast_extractor import (
    extract_class_with_dep_members,
    extract_symbol_from_ast,
    find_used_attrs_on_module,
    resolve_module_local_name,
    resolve_symbol_file,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
DEVEVAL_DIR = BASE_DIR / "DevEval"
SOURCE_CODE_DIR = DEVEVAL_DIR / "Source_Code"
DATA_JSONL = BASE_DIR / "data_filtered.jsonl"
PROMPT_FILE = (
    DEVEVAL_DIR
    / "Experiments"
    / "prompt"
    / "without_context"
    / "gpt-4-1106_prompt.jsonl"
)
OUTPUT_DIR = BASE_DIR / "output" / "prompt"

# ---------------------------------------------------------------------------
# Dependency extraction (bridges ast_extractor.py)
# ---------------------------------------------------------------------------


def extract_dependency_code(
    project_path: str,
    symbol: str,
    func_mode: str = "full",
    class_mode: str = "full",
    target_func_file: Optional[str] = None,
    body_position: Optional[list[int]] = None,
) -> Optional[str]:
    """Resolve a DevEval dependency symbol and extract its source."""
    repo_path = str(SOURCE_CODE_DIR / project_path)
    if not os.path.isdir(repo_path):
        return None

    file_path, remainder = resolve_symbol_file(repo_path, symbol)
    if file_path is None:
        return None

    # Normal case: remainder points to a specific symbol.
    if remainder:
        return extract_symbol_from_ast(file_path, remainder, func_mode, class_mode)

    # Empty remainder = symbol resolved straight to a file. This can mean:
    #   (a) the dep is "this whole module" — used via `import x; x.foo()`
    #   (b) the dep is a top-level variable sharing the file's basename,
    #       e.g. `faker/decode/codes.py` defines `codes = (...)` and is
    #       imported as `from .codes import codes`.

    # (a) Try module-as-name pattern first.
    if target_func_file is not None and body_position is not None:
        local_name = resolve_module_local_name(target_func_file, file_path, symbol)
        if local_name is not None:
            used_attrs = find_used_attrs_on_module(
                target_func_file, body_position, local_name,
            )
            if used_attrs:
                blocks: list[str] = []
                for attr in used_attrs:
                    code = extract_symbol_from_ast(file_path, attr, func_mode, class_mode)
                    if code:
                        blocks.append(code)
                if blocks:
                    return "\n\n".join(blocks)

    # (b) Fallback: extract a top-level symbol whose name matches the file's
    # basename (covers same-name variable/function/class inside the module).
    leaf = symbol.rsplit(".", 1)[-1]
    code = extract_symbol_from_ast(file_path, leaf, func_mode, class_mode)
    if code:
        return code

    return None


# ---------------------------------------------------------------------------
# Context building & prompt injection
# ---------------------------------------------------------------------------


def _resolve_class_member(repo_path: str, symbol: str) -> Optional[tuple[str, str, str]]:
    """Resolve ``symbol`` to ``(file_path, class_name, member_name)`` if it
    refers to a member of a class defined in some file under ``repo_path``.

    Returns ``None`` when ``symbol`` is not a class-member reference (e.g.
    a standalone function, module-level variable, or unresolvable name).
    """
    file_path, remainder = resolve_symbol_file(repo_path, symbol)
    if file_path is None or not remainder:
        return None
    parts = remainder.split(".")
    if len(parts) < 2:
        return None
    # Confirm parts[0] is actually a class in that file (cheap AST check).
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            import ast as _ast
            tree = _ast.parse(fh.read())
        for node in _ast.walk(tree):
            if isinstance(node, _ast.ClassDef) and node.name == parts[0]:
                return file_path, parts[0], parts[1]
    except Exception:
        return None
    return None


def build_context_string(
    sample: dict,
    func_mode: str = "full",
    class_mode: str = "full",
) -> str:
    """Collect all dependency code blocks for a single sample."""
    dep = sample["dependency"]
    project_path = sample["project_path"]
    target_ns = sample.get("namespace")
    target_type = sample.get("type", "function")
    repo_path = str(SOURCE_CODE_DIR / project_path)

    # Identify target's class & method (for redaction in full mode).
    target_class_short: Optional[str] = None
    target_method_name: Optional[str] = None
    if target_type == "method" and target_ns:
        ns_parts = target_ns.split(".")
        target_method_name = ns_parts[-1]
        target_class_short = ns_parts[-2] if len(ns_parts) >= 2 else None

    all_symbols = (
        dep.get("intra_class", [])
        + dep.get("intra_file", [])
        + dep.get("cross_file", [])
    )

    if not all_symbols:
        return ""

    target_func_file = str(
        SOURCE_CODE_DIR / sample["completion_path"]
    ) if "completion_path" in sample else None
    body_position = sample.get("body_position")

    # Dedup + skip self-reference.
    seen: set[str] = set()
    unique_symbols: list[str] = []
    for s in all_symbols:
        if s == target_ns:
            continue
        if s not in seen:
            seen.add(s)
            unique_symbols.append(s)

    # Group Class.member deps so a class is emitted exactly once with all
    # interesting members (and target body redacted if needed).
    class_groups: dict[tuple[str, str], list[str]] = {}
    standalone: list[str] = []
    for sym in unique_symbols:
        resolved = _resolve_class_member(repo_path, sym)
        if resolved is not None:
            file_path, cls_name, member_name = resolved
            class_groups.setdefault((file_path, cls_name), []).append(member_name)
        else:
            standalone.append(sym)

    code_blocks: list[str] = []

    # Class-grouped deps.
    for (file_path, cls_name), members in class_groups.items():
        redact = target_method_name if cls_name == target_class_short else None
        block = extract_class_with_dep_members(
            file_path, cls_name, members,
            mode=class_mode,
            redact_member=redact,
        )
        if block:
            code_blocks.append(block)

    # Remaining (function / variable / module-ref) deps.
    for sym in standalone:
        code = extract_dependency_code(
            project_path, sym, func_mode, class_mode,
            target_func_file=target_func_file,
            body_position=body_position,
        )
        if code:
            code_blocks.append(code)

    # Final code-level dedup.
    seen_blocks: set[str] = set()
    unique_blocks: list[str] = []
    for b in code_blocks:
        if b not in seen_blocks:
            seen_blocks.add(b)
            unique_blocks.append(b)

    return "\n\n".join(unique_blocks)


def inject_context(original_prompt: str, context: str) -> str:
    """Inject dependency context and body-only instruction into the prompt."""
    prompt = original_prompt

    if context:
        marker = "Input Code:"
        idx = prompt.find(marker)
        if idx != -1:
            context_block = (
                "Relevant context:\n"
                "```python\n"
                f"{context}\n"
                "```\n\n"
            )
            prompt = prompt[:idx] + context_block + prompt[idx:]

    prompt = prompt.replace(
        "Completed Code:",
        "Completed Code (output only the function body, without the def line, docstring, or any import statements):",
    )

    return prompt


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate prompt variants and write them to ``output/``."""
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("Loading data.jsonl...")
    data_map: dict[str, dict] = {}
    with open(DATA_JSONL, "r") as f:
        for line in f:
            sample = json.loads(line)
            data_map[sample["namespace"]] = sample

    print(f"Loading prompts from {PROMPT_FILE.name}...")
    prompts: list[dict] = []
    with open(PROMPT_FILE, "r") as f:
        for line in f:
            prompts.append(json.loads(line))

    print(f"  samples (filtered): {len(data_map)}, base prompts (DevEval): {len(prompts)}")

    variants = [
        ("sig_doc", "sig_doc",         "prompt_func-sd_class-sd.jsonl"),
        ("sig_doc", "sd_init",         "prompt_func-sd_class-sd_init.jsonl"),
        ("sig_doc", "full",            "prompt_func-sd_class-full.jsonl"),
        ("full",    "sig_doc",         "prompt_func-full_class-sd.jsonl"),
        ("full",    "full",            "prompt_func-full_class-full.jsonl"),
        # Focused variants: only the requested dep members are shown
        # (no full class skeleton with unrelated siblings).
        ("sig_doc", "sig_doc_focused", "prompt_func-sd_class-sd_focused.jsonl"),
        ("sig_doc", "sd_init_focused", "prompt_func-sd_class-sd_init_focused.jsonl"),
        ("full",    "full_focused",    "prompt_func-full_class-full_focused.jsonl"),
    ]

    valid_namespaces: list[str] = []

    for idx, (func_mode, class_mode, out_name) in enumerate(variants):
        out_path = OUTPUT_DIR / out_name
        print(f"\nGenerating {out_name} (func={func_mode}, class={class_mode})...")

        total = 0
        with_context = 0
        skipped = 0

        with open(out_path, "w") as fout:
            for prompt_entry in prompts:
                ns = prompt_entry["namespace"]
                sample = data_map.get(ns)

                if sample is None:
                    skipped += 1
                    continue

                context = build_context_string(sample, func_mode, class_mode)
                new_prompt = inject_context(prompt_entry["prompt"], context)

                output_entry = {"namespace": ns, "prompt": new_prompt}
                fout.write(json.dumps(output_entry, ensure_ascii=False) + "\n")
                total += 1
                if context:
                    with_context += 1

                if idx == 0:
                    valid_namespaces.append(ns)

        print(f"  Done: {total} prompts ({with_context} with context), {skipped} skipped (no match in data)")
        print(f"  Saved to {out_path}")

    # Filter baseline prompts to the same namespace set.
    valid_ns = set(valid_namespaces)
    baseline_sources = {
        "without_context": DEVEVAL_DIR / "Experiments" / "prompt" / "without_context" / "gpt-4-1106_prompt.jsonl",
        "local_infilling": DEVEVAL_DIR / "Experiments" / "prompt" / "local_infilling" / "gpt-4-1106_prompt.jsonl",
    }

    print("\nFiltering baseline prompts...")
    for label, src_path in baseline_sources.items():
        if not src_path.exists():
            print(f"  {label}: source not found ({src_path}), skipping")
            continue

        out_path = OUTPUT_DIR / f"prompt_{label}.jsonl"
        written = 0
        with open(src_path, "r") as fin, open(out_path, "w") as fout:
            for line in fin:
                entry = json.loads(line)
                if entry["namespace"] in valid_ns:
                    fout.write(line)
                    written += 1
        print(f"  {label}: {written} prompts, saved to {out_path}")


if __name__ == "__main__":
    main()
