#!/usr/bin/env bash
set -euo pipefail

MODEL="gpt-5.4-mini"
API_KEY_FILE="api_key.txt"
WORKERS=40

DEVEVAL_DIR="DevEval"
SOURCE_CODE_ROOT="${DEVEVAL_DIR}/Source_Code"
DATA_FILE="${DEVEVAL_DIR}/data.jsonl"

# -------------------------------------------------------
# 1. Build hydra prompts (1825 full samples)
# -------------------------------------------------------
echo "=== Building hydra prompts (1825 samples) ==="
# python build_hydra_prompt.py --full

# -------------------------------------------------------
# 2. Inference + Evaluate (using pass_k_verbose for stderr)
# -------------------------------------------------------
OUTPUT_BASE="output_full/generated_code"

# for VARIANT in hydra_dar hydra_dar_bm25; do
for VARIANT in hydra_dar; do
    PROMPT_FILE="output_full/prompt/prompt_${VARIANT}.jsonl"
    OUT_DIR="${OUTPUT_BASE}/${VARIANT}/${MODEL}"

    echo ""
    echo "=========================================="
    echo "  [${VARIANT}] Inference (1825 samples)"
    echo "=========================================="
    # python inference.py \
    #     --prompt_file "$PROMPT_FILE" \
    #     --output_dir "$OUT_DIR" \
    #     --model "$MODEL" \
    #     --api_key_file "$API_KEY_FILE"

    echo ""
    echo "=========================================="
    echo "  [${VARIANT}] Evaluate"
    echo "=========================================="
    python pass_k_verbose.py \
        --output_file "${OUT_DIR}/completion.jsonl" \
        --log_file "${OUT_DIR}/log.jsonl" \
        --source_code_root "$SOURCE_CODE_ROOT" \
        --data_file "$DATA_FILE" \
        --workers "$WORKERS"
done

echo ""
echo "=== All done ==="
