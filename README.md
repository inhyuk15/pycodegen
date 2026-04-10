# DevEval AST Context Prompt Builder

Extracts dependency function source code via AST parsing using DevEval's ground-truth dependency annotations, and injects it as context into code completion prompts. No retriever (BM25, DAR, etc.) is needed — dependencies are already specified in `data.jsonl`.

Two prompt variants are generated:
- **sig_doc** — dependency function signatures + docstrings only
- **full_body** — complete dependency function source code

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

### 1. Build prompts

```bash
python build_prompt.py
```

### 2. Run inference

```bash
MODEL=gpt-5.4-mini
VARIANT=sig_doc  # or full_body

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

### 3. Evaluate

```bash
python DevEval/pass_k.py \
    --output_file DevEval/Experiments/${VARIANT}/${MODEL}/completion.jsonl \
    --log_file DevEval/Experiments/${VARIANT}/${MODEL}/log.jsonl \
    --source_code_root DevEval/Source_Code \
    --data_file DevEval/data.jsonl
```
