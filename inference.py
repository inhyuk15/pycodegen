"""Generate code completions for DevEval prompts via OpenAI API.

Reads a JSONL prompt file, calls the chat completions API with greedy
decoding (temperature=0), and writes results to the output directory.
Supports resume and ``--limit`` for partial runs.

Adapted from EvoCodeBench (https://github.com/seketeam/EvoCodeBench).
"""

from __future__ import annotations

import argparse
import json
import os
import time

from openai import OpenAI
from tqdm import tqdm


def clean_completion(code: str) -> str:
    """Strip markdown fences, leading def line, and docstring from a completion.

    DevEval's pass_k.py replaces only the function *body* (after the
    signature and docstring).  Models tend to echo the def line and
    docstring back, so both must be removed to avoid duplication.
    """
    lines = code.splitlines()

    # Remove opening ```python fence.
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]

    # Remove everything from closing ``` onward.
    result = []
    for line in lines:
        if line.strip().startswith("```"):
            break
        result.append(line)
    lines = result

    # Remove leading def line (model often echoes the signature).
    if lines and lines[0].strip().startswith("def "):
        lines = lines[1:]

    # Remove leading docstring (triple-quoted block).
    if lines:
        first = lines[0].strip()
        if first.startswith('"""') or first.startswith("'''"):
            quote = first[:3]
            # Single-line docstring: """..."""
            if first.count(quote) >= 2 and first.endswith(quote) and len(first) > 3:
                lines = lines[1:]
            else:
                # Multi-line docstring: find closing triple quote.
                i = 1
                while i < len(lines):
                    if quote in lines[i]:
                        lines = lines[i + 1 :]
                        break
                    i += 1
                else:
                    # No closing quote found — leave as is.
                    pass

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt_file", type=str, required=True)
    parser.add_argument("--output_dir", type=str, required=True)
    parser.add_argument("--model", type=str, required=True)
    parser.add_argument("--api_key_file", type=str, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max number of samples to process.")
    args = parser.parse_args()

    with open(args.api_key_file) as f:
        api_key = f.read().strip()

    client = OpenAI(api_key=api_key)
    os.makedirs(args.output_dir, exist_ok=True)
    output_path = os.path.join(args.output_dir, "completion.jsonl")

    # Load already-finished namespaces for resume support.
    finished: set[str] = set()
    if os.path.exists(output_path):
        with open(output_path) as f:
            for line in f:
                finished.add(json.loads(line)["namespace"])

    with open(args.prompt_file) as f:
        samples = [json.loads(line) for line in f]

    if args.limit is not None:
        samples = samples[:args.limit]

    print(f"Total: {len(samples)}, already done: {len(finished)}")

    with open(output_path, "a") as fout:
        for sample in tqdm(samples):
            if sample["namespace"] in finished:
                continue

            while True:
                try:
                    resp = client.chat.completions.create(
                        model=args.model,
                        messages=[{"role": "user", "content": sample["prompt"]}],
                        temperature=0,
                    )
                    break
                except Exception as e:
                    print(f"Error: {e}, retrying in 5s...")
                    time.sleep(5)

            result = {
                "namespace": sample["namespace"],
                "completion": clean_completion(resp.choices[0].message.content),
            }
            fout.write(json.dumps(result) + "\n")
            fout.flush()


if __name__ == "__main__":
    main()
