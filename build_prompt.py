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
OUTPUT_DIR = BASE_DIR / "output"

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

    # Module reference: find which attrs are actually used in the target body.
    if target_func_file is None or body_position is None:
        return None

    local_name = resolve_module_local_name(target_func_file, file_path, symbol)
    if local_name is None:
        return None

    used_attrs = find_used_attrs_on_module(
        target_func_file, body_position, local_name,
    )
    if not used_attrs:
        return None

    blocks: list[str] = []
    for attr in used_attrs:
        code = extract_symbol_from_ast(file_path, attr, func_mode, class_mode)
        if code:
            blocks.append(code)
    return "\n\n".join(blocks) if blocks else None


# ---------------------------------------------------------------------------
# Context building & prompt injection
# ---------------------------------------------------------------------------


def build_context_string(
    sample: dict,
    func_mode: str = "full",
    class_mode: str = "full",
) -> str:
    """Collect all dependency code blocks for a single sample."""
    dep = sample["dependency"]
    project_path = sample["project_path"]

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

    seen: set[str] = set()
    unique_symbols: list[str] = []
    for s in all_symbols:
        if s not in seen:
            seen.add(s)
            unique_symbols.append(s)

    code_blocks: list[str] = []
    for sym in unique_symbols:
        code = extract_dependency_code(
            project_path, sym, func_mode, class_mode,
            target_func_file=target_func_file,
            body_position=body_position,
        )
        if code:
            code_blocks.append(code)

    return "\n\n".join(code_blocks)


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
        ("sig_doc", "sig_doc", "prompt_func-sd_class-sd.jsonl"),
        ("sig_doc", "full",    "prompt_func-sd_class-full.jsonl"),
        ("full",    "sig_doc", "prompt_func-full_class-sd.jsonl"),
        ("full",    "full",    "prompt_func-full_class-full.jsonl"),
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

    # Write valid_namespaces.txt for stage2 filtering of baseline prompts.
    ns_path = OUTPUT_DIR / "valid_namespaces.txt"
    with open(ns_path, "w") as f:
        for ns in valid_namespaces:
            f.write(ns + "\n")
    print(f"\nSaved {len(valid_namespaces)} valid namespaces to {ns_path}")


if __name__ == "__main__":
    main()
