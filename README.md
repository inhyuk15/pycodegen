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
    --prompt_file output/prompt/prompt_${VARIANT}.jsonl \
    --output_dir output/generated_code/${VARIANT}/${MODEL} \
    --model ${MODEL} \
    --api_key_file api_key.txt
```

To test with a subset first:

```bash
python inference.py \
    --prompt_file output/prompt/prompt_${VARIANT}.jsonl \
    --output_dir output/generated_code/${VARIANT}/${MODEL} \
    --model ${MODEL} \
    --api_key_file api_key.txt \
    --limit 10
```

### 4. Evaluate

```bash
python DevEval/pass_k.py \
    --output_file output/generated_code/${VARIANT}/${MODEL}/completion.jsonl \
    --log_file output/generated_code/${VARIANT}/${MODEL}/log.jsonl \
    --source_code_root DevEval/Source_Code \
    --data_file DevEval/data.jsonl
```

## Hydra Comparison

To compare against [Hydra](https://arxiv.org/abs/2602.11671) using the same model and data:

### Setup

```bash
# Unzip hydra into project root
python3 -m zipfile -e hydra-7F01.zip hydra
```

Hydra requires DevEval Source_Code under `hydra/benchmark/DevEval/Source_Code/`. If not present, copy or symlink from DevEval:

```bash
cp -r DevEval/Source_Code hydra/benchmark/DevEval/Source_Code
```

### 1. Parse repositories (slow — takes several hours)

```bash
cd hydra
bash src/context_formulation/structured_indexer/run.sh --dataset DevEval
cd ..
```

This generates `hydra/data/parser_output/DevEval/{repo}/dependency_graph.json` for all 115 repos.

### 2. Process benchmark

```bash
cd hydra
PYTHONPATH="src/:$PYTHONPATH" python src/retriever/load_benchmark.py --benchmark DevEval
cd ..
```

Generates `hydra/data/processed_benchmarks/processed_DevEval.jsonl` (1,825 samples).

### 3. Build hydra-format prompts

```bash
python build_hydra_prompt.py
```

Uses ground-truth dependencies (DAR recall=1.0) to build hydra-format prompts, filtered to our 1,323 samples:
- `output/prompt/prompt_hydra_dar.jsonl` — ground-truth dependencies only
- `output/prompt/prompt_hydra_dar_bm25.jsonl` — ground-truth + BM25 top-5

### 4. Run inference & evaluate

```bash
MODEL=gpt-5.4-mini

for VARIANT in hydra_dar hydra_dar_bm25; do
    python inference.py \
        --prompt_file output/prompt/prompt_${VARIANT}.jsonl \
        --output_dir output/generated_code/${VARIANT}/${MODEL} \
        --model ${MODEL} \
        --api_key_file api_key.txt

    python DevEval/pass_k.py \
        --output_file output/generated_code/${VARIANT}/${MODEL}/completion.jsonl \
        --log_file output/generated_code/${VARIANT}/${MODEL}/log.jsonl \
        --source_code_root DevEval/Source_Code \
        --data_file DevEval/data.jsonl
done
```

## File Structure

```
.
├── filter_data.py           # Filter data.jsonl → data_filtered.jsonl
├── ast_extractor.py         # AST-based symbol resolution & source extraction
├── build_prompt.py          # Prompt builder (context injection + baseline filtering)
├── build_hydra_prompt.py    # Hydra-format prompt builder (GT deps + optional BM25)
├── inference.py             # LLM inference runner
├── run_all.sh               # Full pipeline (filter → build → inference → evaluate)
├── data_filtered.jsonl      # (generated) samples with dependencies (1,323/1,825)
├── output/
│   ├── prompt/              # Generated prompts
│   │   ├── prompt_without_context.jsonl
│   │   ├── prompt_local_infilling.jsonl
│   │   ├── prompt_func-sd_class-sd.jsonl
│   │   ├── prompt_func-full_class-full.jsonl
│   │   ├── prompt_hydra_dar.jsonl
│   │   └── prompt_hydra_dar_bm25.jsonl
│   └── generated_code/      # Inference results
│       ├── without_context/{model}/
│       ├── local_infilling/{model}/
│       ├── func-sd_class-sd/{model}/
│       ├── func-full_class-full/{model}/
│       ├── hydra_dar/{model}/
│       └── hydra_dar_bm25/{model}/
├── hydra/                   # Hydra (unzipped from hydra-7F01.zip)
├── DevEval/                 # External (cloned separately)
│   ├── data.jsonl
│   └── Source_Code/
└── requirements.txt
```
