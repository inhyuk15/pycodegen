# DevEval AST Context Prompt Builder

Extracts dependency source code (functions, classes, variables) via AST parsing using DevEval's ground-truth dependency annotations, and injects it as context into code completion prompts. No retriever (BM25, DAR, etc.) is needed — dependencies are already specified in `data.jsonl`.

## Prompt Variants

Function/method mode and class mode are independently configurable:

| Variant | func_mode | class_mode | Description |
|---|---|---|---|
| `func-sd_class-sd` | sig_doc | sig_doc | Signatures + docstrings only |
| `func-sd_class-sd_init` | sig_doc | sd_init | `sig_doc` but `__init__` shown in full |
| `func-sd_class-full` | sig_doc | full | Function signatures, full class source |
| `func-full_class-sd` | full | sig_doc | Full function source, class signatures |
| `func-full_class-full` | full | full | Full source for everything |

- **sig_doc (functions)** — signature + docstring + `...`
- **sig_doc (classes)** — class signature + docstring + member signatures + class-level attributes
- **sd_init (classes)** — same as `sig_doc` but `__init__` body is shown in full
- **full** — complete source code
- **variables/constants** — always emitted as-is (assignment statement)

Samples with no dependencies are filtered out (`data_filtered.jsonl`) since they are identical to DevEval's `without_context` baseline.

## Setup

### 1. Clone and create Python env

```bash
git clone https://github.com/YOUR_USERNAME/python_code_gen_test.git
cd python_code_gen_test

conda create --name deveval python=3.9 -y
conda activate deveval
pip install -r requirements.txt
```

### 2. Fetch DevEval data

```bash
git clone https://github.com/seketeam/DevEval.git
cd DevEval
wget https://huggingface.co/datasets/LJ0815/DevEval/resolve/main/Source_Code.tar.gz
wget https://huggingface.co/datasets/LJ0815/DevEval/resolve/main/data.tar.gz
tar -xzvf Source_Code.tar.gz
tar -xzvf data.tar.gz
cd ..

echo "sk-YOUR_KEY" > api_key.txt
```

### 3. Fix Source_Code permissions (if needed)

If `Source_Code.tar.gz` was extracted with a different user, fix ownership so tests can write to the repos:

```bash
sudo chown -R "$(id -u):$(id -g)" DevEval/Source_Code
```

### 4. Install per-repo virtual environments

DevEval's original `python setup.py pytest` mechanism is deprecated in modern
setuptools and produces `.eggs/` race conditions when evaluated in parallel.
Instead, we create **one venv per repo** (115 total) so that each repo's
dependencies live in their own `site-packages`:

```bash
bash setup_venvs.sh
```

- Creates `DevEval/.venvs/<repo_name>/` for each of the 115 repos
- Inherits packages from the active conda env via `--system-site-packages`
- Installs the repo in editable mode (`pip install -e .`)
- ~5 repos may fail to install (logged to `setup_venvs_failed.txt`);
  these are handled in the next step

Override parallelism with `PARALLEL=40 bash setup_venvs.sh` if you have
many cores.

### 5. Patch known venv issues

Some repos need test-time dependencies or version pins that `pip install -e .`
does not install automatically. Apply the fixes below:

```bash
# Test-time deps missing from install_requires
DevEval/.venvs/zulip-term/bin/pip install pytest-mock
DevEval/.venvs/datasette/bin/pip install trustme
DevEval/.venvs/kinto/bin/pip install webtest statsd
DevEval/.venvs/sacred/bin/pip install 'mock>=3.0,<5.0'
DevEval/.venvs/pyramid/bin/pip install zope.component webtest
DevEval/.venvs/mrjob/bin/pip install warcio
DevEval/.venvs/falcon/bin/pip install pyyaml
DevEval/.venvs/alembic/bin/pip install psycopg2-binary
DevEval/.venvs/bentoml/bin/pip install scipy

# Version pins (new APIs removed symbols these repos need)
DevEval/.venvs/barf/bin/pip install 'capstone<5'
DevEval/.venvs/mongoengine/bin/pip install 'pymongo<4'

# NLTK data for summarizer tests
DevEval/.venvs/sumy/bin/python -c "
import nltk
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)
nltk.download('stopwords', quiet=True)
"

# cupy: use prebuilt CUDA 12 wheel (source build fails without CUDA dev headers)
DevEval/.venvs/cupy/bin/pip install cupy-cuda12x
```

Repos with genuinely broken build scripts (`PySimpleSOAP`) are skipped — the
2 affected samples are reported as infrastructure failures.

### 6. Verify the environment

```bash
# Shared tooling (pytest-cov is needed by some repos, pandas by bentoml tests)
pip install pytest-cov pytest-mock pandas

# Ensure ground-truth code passes tests
python pass_k_verbose.py \
    --source_code_root DevEval/Source_Code \
    --data_file DevEval/data.jsonl
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

Reads `data_filtered.jsonl` and generates five prompt variants under `output/prompt/`.

### 3. Run inference

```bash
MODEL=gpt-5.4-mini
VARIANT=func-sd_class-sd  # or func-sd_class-sd_init, func-sd_class-full, func-full_class-sd, func-full_class-full

python inference.py \
    --prompt_file output/prompt/prompt_${VARIANT}.jsonl \
    --output_dir output/generated_code/${MODEL}/${VARIANT} \
    --model ${MODEL} \
    --api_key_file api_key.txt
```

Add `--limit 10` for a quick sanity check.

### 4. Evaluate

`pass_k_verbose.py` replaces DevEval's `pass_k.py`. Key differences:

- Uses each repo's per-repo venv Python (`DevEval/.venvs/<repo>/bin/python`)
- Calls `python -m pytest` instead of `python setup.py pytest`
- Captures both stdout and stderr with setuptools noise filtered out
- Runs in parallel with project-level `flock` to prevent source-file races

```bash
python pass_k_verbose.py \
    --output_file output/generated_code/${MODEL}/${VARIANT}/completion.jsonl \
    --log_file output/generated_code/${MODEL}/${VARIANT}/log.jsonl \
    --source_code_root DevEval/Source_Code \
    --data_file DevEval/data.jsonl \
    --workers 40
```

Or use `./run_exec.sh` to run inference + evaluation for all variants.

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
python build_hydra_prompt.py --full
```

Uses outgoing_calls from hydra's dependency graph (DAR recall=1.0 simulation) to build hydra-format prompts for all 1,825 samples:
- `output_full/prompt/prompt_hydra_dar.jsonl` — outgoing_calls only (perfect DAR)
- `output_full/prompt/prompt_hydra_dar_bm25.jsonl` — outgoing_calls + BM25 top-5

### 4. Run inference & evaluate

```bash
MODEL=gpt-5.4-mini

for VARIANT in hydra_dar hydra_dar_bm25; do
    python inference.py \
        --prompt_file output_full/prompt/prompt_${VARIANT}.jsonl \
        --output_dir output_full/generated_code/${MODEL}/${VARIANT} \
        --model ${MODEL} \
        --api_key_file api_key.txt

    python pass_k_verbose.py \
        --output_file output_full/generated_code/${MODEL}/${VARIANT}/completion.jsonl \
        --log_file output_full/generated_code/${MODEL}/${VARIANT}/log.jsonl \
        --source_code_root DevEval/Source_Code \
        --data_file DevEval/data.jsonl \
        --workers 40
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
├── pass_k_verbose.py        # Parallel, venv-aware evaluator (replaces DevEval pass_k.py)
├── setup_venvs.sh           # Creates per-repo venvs under DevEval/.venvs/
├── run_exec.sh              # Inference + evaluation for all variants
├── run_all.sh               # Full pipeline (filter → build → inference → evaluate)
├── data_filtered.jsonl      # (generated) samples with dependencies (1,323/1,825)
├── output/
│   ├── prompt/              # Generated prompts
│   │   ├── prompt_without_context.jsonl
│   │   ├── prompt_local_infilling.jsonl
│   │   ├── prompt_func-sd_class-sd.jsonl
│   │   ├── prompt_func-sd_class-sd_init.jsonl
│   │   ├── prompt_func-sd_class-full.jsonl
│   │   ├── prompt_func-full_class-sd.jsonl
│   │   └── prompt_func-full_class-full.jsonl
│   └── generated_code/
│       └── {model}/
│           ├── without_context/{completion.jsonl,log.jsonl}
│           ├── local_infilling/{completion.jsonl,log.jsonl}
│           ├── func-sd_class-sd/{completion.jsonl,log.jsonl}
│           ├── func-sd_class-sd_init/{completion.jsonl,log.jsonl}
│           ├── func-sd_class-full/{completion.jsonl,log.jsonl}
│           ├── func-full_class-sd/{completion.jsonl,log.jsonl}
│           └── func-full_class-full/{completion.jsonl,log.jsonl}
├── output_full/             # Hydra comparison (1,825 samples, no dep filtering)
│   ├── prompt/
│   └── generated_code/{model}/{variant}/
├── hydra/                   # Hydra (unzipped from hydra-7F01.zip)
├── DevEval/                 # External (cloned separately)
│   ├── data.jsonl
│   ├── Source_Code/         # 115 repo sources
│   └── .venvs/              # (generated) 115 per-repo venvs
└── requirements.txt
```
