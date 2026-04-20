"""Build hydra-format prompts using outgoing_calls from dependency_graph.json.

Simulates hydra with perfect DAR (recall=1.0) by directly using
outgoing_calls from hydra's AST-parsed dependency graph, bypassing
the DAR model entirely. Optionally adds BM25 results on top.

Produces two prompt variants:
  - outgoing_calls only: perfect DAR simulation
  - outgoing_calls + BM25: perfect DAR + BM25 top-5

Requires:
  - hydra's processed_DevEval.jsonl (from load_benchmark.py)
  - hydra's parser_output/DevEval/*/dependency_graph.json

Usage::

    python build_hydra_prompt.py          # 1323 filtered samples → output/prompt/
    python build_hydra_prompt.py --full   # 1825 all samples → output_full/prompt/
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from rank_bm25 import BM25Okapi

BASE_DIR = Path(__file__).parent
DATA_FILTERED = BASE_DIR / "data_filtered.jsonl"
HYDRA_DIR = BASE_DIR / "hydra"
PROCESSED_DEVEVAL = HYDRA_DIR / "data" / "processed_benchmarks" / "processed_DevEval.jsonl"
PARSER_OUTPUT_DIR = HYDRA_DIR / "data" / "parser_output" / "DevEval"


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_processed_deveval() -> dict[str, dict]:
    """Load hydra's processed DevEval samples, keyed by id (namespace)."""
    samples = {}
    with open(PROCESSED_DEVEVAL) as f:
        for line in f:
            sample = json.loads(line)
            samples[sample["id"]] = sample
    return samples


def load_all_dependency_graphs() -> dict[str, dict]:
    """Load all dependency_graph.json files, keyed by component ID."""
    all_components: dict[str, dict] = {}
    for repo_dir in PARSER_OUTPUT_DIR.iterdir():
        if not repo_dir.is_dir():
            continue
        dg_path = repo_dir / "dependency_graph.json"
        if not dg_path.exists():
            continue
        with open(dg_path) as f:
            dg = json.load(f)
        all_components.update(dg)
    return all_components


def load_filtered_namespaces() -> list[str]:
    """Load ordered namespaces from our filtered prompt file (1323 samples)."""
    ref_prompt = BASE_DIR / "output" / "prompt" / "prompt_func-full_class-full.jsonl"
    ordered = []
    with open(ref_prompt) as f:
        for line in f:
            ordered.append(json.loads(line)["namespace"])
    return ordered


# ---------------------------------------------------------------------------
# Namespace → component ID resolution (same logic as load_benchmark.py)
# ---------------------------------------------------------------------------

def resolve_component_id(
    namespace: str,
    sample: dict,
    all_components: dict[str, dict],
) -> str | None:
    """Resolve a DevEval namespace to a dependency_graph component ID."""
    sample_type = sample["type"]
    relative_path = sample["relative_path"]

    if sample_type == "function":
        func_name = namespace.split(".")[-1]
        candidates = [
            f"{func_name}@{relative_path}",
            f"{func_name}@src/{relative_path}",
        ]
    else:  # method
        parts = namespace.split(".")
        method_part = ".".join(parts[-2:])
        file_path = "/".join(parts[:-2]) + ".py"
        init_path = "/".join(parts[:-2]) + "/__init__.py"
        candidates = [
            f"{method_part}@{file_path}",
            f"{method_part}@src/{file_path}",
            f"{method_part}@{init_path}",
            f"{method_part}@src/{init_path}",
            f"{method_part}@{relative_path}",
        ]

    for cid in candidates:
        if cid in all_components:
            return cid
    return None


# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------

def select_outgoing_candidates(
    candidate_pool: dict,
    outgoing_calls: dict,
) -> dict:
    """Select candidates that are in outgoing_calls."""
    # Build set of outgoing_call IDs
    oc_ids: set[str] = set()
    for ctype in ["class", "function", "variable"]:
        for oc_id in outgoing_calls.get(ctype, []):
            oc_ids.add(oc_id)

    result: dict[str, dict[str, dict]] = {"class": {}, "function": {}, "variable": {}}
    for ctype in ["class", "function", "variable"]:
        for cid, cinfo in candidate_pool.get(ctype, {}).items():
            if cid in oc_ids:
                result[ctype][cid] = cinfo
    return result


def retrieve_bm25(example: dict, top_k: int = 5) -> dict:
    """BM25 retrieval from candidates (same as hydra's implementation)."""
    query = example["target_function_prompt"]
    candidate = example["candidate"]

    corpus_data = []
    for ctype in ["class", "function", "variable"]:
        for cid, cinfo in candidate.get(ctype, {}).items():
            text = cinfo.get("source_code", "")
            corpus_data.append((text, {"type": ctype, "id": cid, **cinfo}))

    if not corpus_data:
        return {}

    corpus_texts = [item[0] for item in corpus_data]
    tokenized_corpus = [text.split() for text in corpus_texts]
    tokenized_query = query.split()

    bm25 = BM25Okapi(tokenized_corpus, k1=1.5, b=0.75)
    scores = bm25.get_scores(tokenized_query)

    scored_items = sorted(
        [{"score": scores[i], "metadata": m} for i, (_, m) in enumerate(corpus_data)],
        key=lambda x: x["score"],
        reverse=True,
    )[:top_k]

    results = defaultdict(lambda: {"class": {}, "function": {}, "variable": {}})
    for item in scored_items:
        m = item["metadata"]
        results[m["relative_path"]][m["type"]][m["id"]] = {
            "relative_path": m["relative_path"],
            "source_code": m.get("source_code", ""),
        }
    return dict(results)


def merge_results(a: dict, b: dict) -> dict:
    """Merge two result dicts (union)."""
    merged = defaultdict(lambda: {"class": {}, "function": {}, "variable": {}})
    for results in [a, b]:
        for file_path, types in results.items():
            for ctype in ["class", "function", "variable"]:
                for cid, cinfo in types.get(ctype, {}).items():
                    merged[file_path][ctype][cid] = cinfo
    return dict(merged)


# ---------------------------------------------------------------------------
# Prompt formatting (identical to hydra's retriever.py format_prompt)
# ---------------------------------------------------------------------------

def candidates_to_results(selected: dict) -> dict:
    """Convert selected candidates into results grouped by file path."""
    results = defaultdict(lambda: {"class": {}, "function": {}, "variable": {}})
    for ctype in ["class", "function", "variable"]:
        for cid, cinfo in selected.get(ctype, {}).items():
            fpath = cinfo.get("relative_path", "")
            results[fpath][ctype][cid] = {
                "relative_path": fpath,
                "source_code": cinfo.get("source_code", ""),
            }
    return dict(results)


def format_hydra_prompt(example: dict, results: dict) -> str:
    """Format prompt in hydra's exact format."""
    component_type = example["type"]
    current_file_path = example["relative_path"]

    prompt_elements = [
        "You are a Python programmer working with a repository. "
        "Here is all the context you may find useful to complete the function:"
    ]

    current_file_results = {}
    other_file_results = {}

    for file_path, file_results in results.items():
        if file_path == current_file_path:
            current_file_results = file_results
        else:
            other_file_results[file_path] = file_results

    for file_path, file_results in other_file_results.items():
        prompt_elements.append(f"#FILE: {file_path}")
        for ctype in ["class", "variable", "function"]:
            if file_results.get(ctype):
                for _, cinfo in file_results[ctype].items():
                    prompt_elements.append(cinfo["source_code"])
                    prompt_elements.append("")

    if current_file_results:
        prompt_elements.append(f"#CURRENT FILE: {current_file_path}")
        import_stmts = example.get("import_statements", [])
        if import_stmts:
            for stmt in import_stmts:
                prompt_elements.append(stmt)
            prompt_elements.append("")
        for ctype in ["class", "variable", "function"]:
            if current_file_results.get(ctype):
                for _, cinfo in current_file_results[ctype].items():
                    prompt_elements.append(cinfo["source_code"])
                    prompt_elements.append("")

    prompt_elements.append(
        "Based on the information above, please complete the function in the current file:"
    )
    t_f_p = (
        example["target_function_prompt"]
        if component_type == "function"
        else example["target_method_prompt"]
    )
    prompt_elements.append(t_f_p)

    return "\n".join(prompt_elements)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Build hydra-format prompts")
    parser.add_argument(
        "--full", action="store_true",
        help="Use all 1825 samples (output_full/). Default: 1323 filtered (output/).",
    )
    args = parser.parse_args()

    if args.full:
        output_dir = BASE_DIR / "output_full" / "prompt"
    else:
        output_dir = BASE_DIR / "output" / "prompt"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading dependency graphs...")
    all_components = load_all_dependency_graphs()
    print(f"  {len(all_components)} components loaded")

    print("Loading processed DevEval...")
    processed = load_processed_deveval()
    print(f"  {len(processed)} samples")

    if args.full:
        ordered_ns = list(processed.keys())
        print(f"  Mode: full ({len(ordered_ns)} samples)")
    else:
        ordered_ns = load_filtered_namespaces()
        print(f"  Mode: filtered ({len(ordered_ns)} samples)")

    oc_only_path = output_dir / "prompt_hydra_dar.jsonl"
    oc_bm25_path = output_dir / "prompt_hydra_dar_bm25.jsonl"

    oc_only_count = 0
    oc_bm25_count = 0
    resolved = 0
    unresolved = 0

    with open(oc_only_path, "w") as f_oc, open(oc_bm25_path, "w") as f_hybrid:
        for ns in ordered_ns:
            if ns not in processed:
                continue

            example = processed[ns]

            # Resolve namespace to component ID
            comp_id = resolve_component_id(ns, example, all_components)

            if comp_id:
                resolved += 1
                outgoing_calls = all_components[comp_id].get(
                    "outgoing_calls", {"class": [], "function": [], "variable": []}
                )
                selected = select_outgoing_candidates(example["candidate"], outgoing_calls)
            else:
                unresolved += 1
                selected = {"class": {}, "function": {}, "variable": {}}

            # Outgoing calls only
            oc_results = candidates_to_results(selected)
            oc_prompt = format_hydra_prompt(example, oc_results)
            entry_oc = {"namespace": ns, "prompt": oc_prompt}
            f_oc.write(json.dumps(entry_oc, ensure_ascii=False) + "\n")
            oc_only_count += 1

            # Outgoing calls + BM25
            bm25_results = retrieve_bm25(example, top_k=5)
            merged = merge_results(oc_results, bm25_results)
            hybrid_prompt = format_hydra_prompt(example, merged)
            entry_hybrid = {"namespace": ns, "prompt": hybrid_prompt}
            f_hybrid.write(json.dumps(entry_hybrid, ensure_ascii=False) + "\n")
            oc_bm25_count += 1

    print(f"\nComponent ID resolved: {resolved}, unresolved: {unresolved}")
    print(f"Outgoing calls only: {oc_only_count} prompts → {oc_only_path}")
    print(f"OC + BM25:           {oc_bm25_count} prompts → {oc_bm25_path}")


if __name__ == "__main__":
    main()
