"""Build hydra-format prompts using ground-truth dependencies.

Simulates hydra's retrieval pipeline with DAR recall=1.0 by using
DevEval's ground-truth dependency annotations instead of the trained
DAR model. Optionally adds BM25 results on top.

Produces two prompt variants:
  - DAR only: ground-truth dependencies in hydra prompt format
  - DAR + BM25: ground-truth + BM25 top-k additional context

Requires:
  - hydra's processed_DevEval.jsonl (from load_benchmark.py)
  - data_filtered.jsonl (our filtered DevEval data with dependencies)

Usage::

    python build_hydra_prompt.py
"""

from __future__ import annotations

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
DEVEVAL_DATA = BASE_DIR / "DevEval" / "data.jsonl"
OUTPUT_DIR = BASE_DIR / "output" / "prompt"


def load_ground_truth() -> dict[str, dict]:
    """Load ground-truth dependencies from data_filtered.jsonl."""
    gt = {}
    with open(DATA_FILTERED) as f:
        for line in f:
            sample = json.loads(line)
            dep = sample["dependency"]
            gt[sample["namespace"]] = {
                "intra_class": dep.get("intra_class", []),
                "intra_file": dep.get("intra_file", []),
                "cross_file": dep.get("cross_file", []),
            }
    return gt


def load_processed_deveval() -> dict[str, dict]:
    """Load hydra's processed DevEval samples, keyed by id (namespace)."""
    samples = {}
    with open(PROCESSED_DEVEVAL) as f:
        for line in f:
            sample = json.loads(line)
            samples[sample["id"]] = sample
    return samples


def match_candidate_to_dependency(
    candidate_id: str,
    dep_symbols: list[str],
) -> bool:
    """Check if a candidate matches any ground-truth dependency symbol.

    candidate_id format: 'name@relative/path.py'
    dep_symbol format: 'module.submodule.ClassName.method'
    """
    # Extract the clean name part from candidate_id
    name_part = candidate_id.split("@")[0] if "@" in candidate_id else candidate_id

    for dep in dep_symbols:
        dep_parts = dep.split(".")
        # Match by last component(s)
        # e.g. dep='boltons.tbutils.TracebackInfo.__init__'
        #      candidate='TracebackInfo.__init__@boltons/tbutils.py'
        if name_part == dep_parts[-1]:
            return True
        if len(dep_parts) >= 2 and name_part == f"{dep_parts[-2]}.{dep_parts[-1]}":
            return True
    return False


def select_gt_candidates(
    candidate: dict,
    dep_symbols: list[str],
) -> dict:
    """Filter candidates to only those matching ground-truth dependencies."""
    result = {"class": {}, "function": {}, "variable": {}}
    for ctype in ["class", "function", "variable"]:
        for cid, cinfo in candidate.get(ctype, {}).items():
            if match_candidate_to_dependency(cid, dep_symbols):
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


def merge_results(dar_results: dict, bm25_results: dict) -> dict:
    """Merge DAR and BM25 results (union)."""
    merged = defaultdict(lambda: {"class": {}, "function": {}, "variable": {}})
    for results in [dar_results, bm25_results]:
        for file_path, types in results.items():
            for ctype in ["class", "function", "variable"]:
                for cid, cinfo in types.get(ctype, {}).items():
                    merged[file_path][ctype][cid] = cinfo
    return dict(merged)


def format_hydra_prompt(
    example: dict,
    results: dict,
) -> str:
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


def dar_results_from_gt(gt_candidates: dict) -> dict:
    """Convert selected GT candidates into the results format (grouped by file)."""
    results = defaultdict(lambda: {"class": {}, "function": {}, "variable": {}})
    for ctype in ["class", "function", "variable"]:
        for cid, cinfo in gt_candidates.get(ctype, {}).items():
            fpath = cinfo.get("relative_path", "")
            results[fpath][ctype][cid] = {
                "relative_path": fpath,
                "source_code": cinfo.get("source_code", ""),
            }
    return dict(results)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading ground-truth dependencies...")
    gt = load_ground_truth()

    print("Loading hydra processed DevEval...")
    processed = load_processed_deveval()

    # Use same namespace order as our prompts
    ref_prompt = OUTPUT_DIR / "prompt_func-full_class-full.jsonl"
    ordered_ns = []
    with open(ref_prompt) as f:
        for line in f:
            ordered_ns.append(json.loads(line)["namespace"])
    valid_ns = set(gt.keys())
    print(f"  Valid namespaces: {len(valid_ns)}")
    print(f"  Processed samples: {len(processed)}")

    dar_only_path = OUTPUT_DIR / "prompt_hydra_dar.jsonl"
    dar_bm25_path = OUTPUT_DIR / "prompt_hydra_dar_bm25.jsonl"

    dar_only_count = 0
    dar_bm25_count = 0
    skipped = 0

    with open(dar_only_path, "w") as f_dar, open(dar_bm25_path, "w") as f_hybrid:
        for ns in ordered_ns:
            if ns not in processed:
                skipped += 1
                continue

            example = processed[ns]
            dep = gt[ns]
            all_dep_symbols = dep["intra_class"] + dep["intra_file"] + dep["cross_file"]

            # DAR only: select GT candidates
            gt_candidates = select_gt_candidates(example["candidate"], all_dep_symbols)
            dar_results = dar_results_from_gt(gt_candidates)
            dar_prompt = format_hydra_prompt(example, dar_results)

            entry_dar = {"namespace": ns, "prompt": dar_prompt}
            f_dar.write(json.dumps(entry_dar, ensure_ascii=False) + "\n")
            dar_only_count += 1

            # DAR + BM25: merge GT with BM25 top-5
            bm25_results = retrieve_bm25(example, top_k=5)
            merged = merge_results(dar_results, bm25_results)
            hybrid_prompt = format_hydra_prompt(example, merged)

            entry_hybrid = {"namespace": ns, "prompt": hybrid_prompt}
            f_hybrid.write(json.dumps(entry_hybrid, ensure_ascii=False) + "\n")
            dar_bm25_count += 1

    print(f"\nDAR only: {dar_only_count} prompts → {dar_only_path}")
    print(f"DAR+BM25: {dar_bm25_count} prompts → {dar_bm25_path}")
    print(f"Skipped (not in processed): {skipped}")


if __name__ == "__main__":
    main()
