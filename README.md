# DevEval AST Context Prompt Builder

Extracts dependency source code (functions, classes, variables) via AST parsing using DevEval's ground-truth dependency annotations, and injects it as context into code completion prompts. No retriever (BM25, DAR, etc.) is needed — dependencies are already specified in `data.jsonl`.

## Prompt Variants

Function/method mode and class mode are independently configurable:

| Variant | func_mode | class_mode | Description |
|---|---|---|---|
| `func-sd_class-sd` | sig_doc | sig_doc | Signatures + docstrings only |
| `func-sd_class-full` | sig_doc | full | Function signatures, full class source |
| `func-full_class-sd` | full | sig_doc | Full function source, class signatures |
| `func-full_class-full` | full | full | Full source for everything |

- **sig_doc (functions)** — signature + docstring + `...`
- **sig_doc (classes)** — class signature + docstring + member signatures + class-level attributes
- **full** — complete source code
- **variables/constants** — always emitted as-is (assignment statement)

Samples with no dependencies are filtered out (`data_filtered.jsonl`) since they are identical to DevEval's `without_context` baseline.

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/python_code_gen_test.git
cd python_code_gen_test

conda create --name deveval python=3.9 -y
conda activate deveval
pip install -r requirements.txt

git clone https://github.com/seketeam/DevEval.git
cd DevEval
wget https://huggingface.co/datasets/LJ0815/DevEval/resolve/main/Source_Code.tar.gz
wget https://huggingface.co/datasets/LJ0815/DevEval/resolve/main/data.tar.gz
tar -xzvf Source_Code.tar.gz
tar -xzvf data.tar.gz
cd ..

echo "sk-YOUR_KEY" > api_key.txt
```

## Usage

### 1. Filter data

```bash
python filter_data.py
```

Filters `DevEval/data.jsonl` → `data_filtered.jsonl` (1,323 samples with dependencies). Samples with no dependencies are excluded since they are identical to the without_context baseline.

### 2. Build prompts

```bash
python build_prompt.py
```

Reads `data_filtered.jsonl` and generates four prompt variants under `output/`.

### 3. Run inference

```bash
MODEL=gpt-5.4-mini
VARIANT=func-sd_class-sd  # or func-sd_class-full, func-full_class-sd, func-full_class-full

python inference.py \
    --prompt_file output/prompt_${VARIANT}.jsonl \
    --output_dir DevEval/Experiments/${VARIANT}/${MODEL} \
    --model ${MODEL} \
    --api_key_file api_key.txt
```

To test with a subset first:

```bash
python inference.py \
    --prompt_file output/prompt_${VARIANT}.jsonl \
    --output_dir DevEval/Experiments/${VARIANT}/${MODEL} \
    --model ${MODEL} \
    --api_key_file api_key.txt \
    --limit 10
```

### 4. Evaluate

```bash
python DevEval/pass_k.py \
    --output_file DevEval/Experiments/${VARIANT}/${MODEL}/completion.jsonl \
    --log_file DevEval/Experiments/${VARIANT}/${MODEL}/log.jsonl \
    --source_code_root DevEval/Source_Code \
    --data_file DevEval/data.jsonl
```

## File Structure

```
.
├── filter_data.py           # Filter data.jsonl → data_filtered.jsonl
├── ast_extractor.py         # AST-based symbol resolution & source extraction
├── build_prompt.py          # Prompt builder (context injection + baseline filtering)
├── inference.py             # LLM inference runner
├── run_all.sh               # Full pipeline (filter → build → inference → evaluate)
├── data_filtered.jsonl      # (generated) samples with dependencies (1,323/1,825)
├── output/
│   ├── prompt/              # Generated prompts
│   │   ├── prompt_without_context.jsonl
│   │   ├── prompt_local_infilling.jsonl
│   │   ├── prompt_func-sd_class-sd.jsonl
│   │   └── prompt_func-full_class-full.jsonl
│   └── generated_code/      # Inference results
│       ├── without_context/{model}/
│       ├── local_infilling/{model}/
│       ├── func-sd_class-sd/{model}/
│       └── func-full_class-full/{model}/
├── DevEval/                 # External (cloned separately)
│   ├── data.jsonl
│   └── Source_Code/
└── requirements.txt
```
