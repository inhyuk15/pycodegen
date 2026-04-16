#!/usr/bin/env bash
set -euo pipefail

MODEL="gpt-5.4-mini"
API_KEY_FILE="api_key.txt"

DEVEVAL_DIR="DevEval"
OUTPUT_BASE="output/generated_code"
SOURCE_CODE_ROOT="${DEVEVAL_DIR}/Source_Code"
DATA_FILE="${DEVEVAL_DIR}/data.jsonl"

# -------------------------------------------------------
# 1. Filter data & build prompts
# -------------------------------------------------------
# echo "=== Stage 1: Filter data.jsonl ==="
# python filter_data.py

# echo "=== Building prompts ==="
# python build_prompt.py

# -------------------------------------------------------
# 2. Define the 4 experiments
#    (label, prompt_file)
# -------------------------------------------------------
declare -a EXPERIMENTS=(
    "without_context|output/prompt/prompt_without_context.jsonl"
    "local_infilling|output/prompt/prompt_local_infilling.jsonl"
    "func-sd_class-sd|output/prompt/prompt_func-sd_class-sd.jsonl"
    "func-full_class-full|output/prompt/prompt_func-full_class-full.jsonl"
)

# -------------------------------------------------------
# 3. Inference + Evaluate
# -------------------------------------------------------
for entry in "${EXPERIMENTS[@]}"; do
    IFS='|' read -r LABEL PROMPT_FILE <<< "$entry"
    OUT_DIR="${OUTPUT_BASE}/${LABEL}/${MODEL}"

    echo ""
    echo "=========================================="
    echo "  [${LABEL}] Inference"
    echo "=========================================="
    python inference.py \
        --prompt_file "$PROMPT_FILE" \
        --output_dir "$OUT_DIR" \
        --model "$MODEL" \
        --api_key_file "$API_KEY_FILE"

    echo ""
    echo "=========================================="
    echo "  [${LABEL}] Evaluate"
    echo "=========================================="
    python "${DEVEVAL_DIR}/pass_k.py" \
        --output_file "${OUT_DIR}/completion.jsonl" \
        --log_file "${OUT_DIR}/log.jsonl" \
        --source_code_root "$SOURCE_CODE_ROOT" \
        --data_file "$DATA_FILE"
done

echo ""
echo "=== All done ==="
