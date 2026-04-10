# DevEval AST Context Prompt Builder

DevEval 벤치마크의 dependency 정보를 활용하여, 관련 함수의 코드를 프롬프트에 삽입하는 도구.

## 핵심 아이디어

DevEval의 `data.jsonl`에는 각 함수가 의존하는 심볼 목록이 명시되어 있다 (`intra_file`, `cross_file`, `intra_class`).
이 정보를 활용해 Source_Code에서 해당 심볼의 실제 코드를 AST로 추출하고, 기존 프롬프트에 context로 삽입한다.

Hydra처럼 BM25/DAR 등의 retriever가 불필요하다 — dependency가 이미 주어져 있으므로.

## Setup

DevEval 데이터는 깃허브에 포함되지 않으므로 직접 다운로드해야 한다.

```bash
cd DevEval
wget https://huggingface.co/datasets/LJ0815/DevEval/resolve/main/Source_Code.tar.gz
wget https://huggingface.co/datasets/LJ0815/DevEval/resolve/main/data.tar.gz

tar -xzvf Source_Code.tar.gz
tar -xzvf data.tar.gz
```

## 출력 프롬프트 두 가지 버전

| 버전 | 파일명 | context 내용 |
|------|--------|-------------|
| sig_doc | `prompt_sig_doc.jsonl` | 의존 함수의 시그니처 + docstring만 |
| full_body | `prompt_full_body.jsonl` | 의존 함수의 전체 코드 |

## 프롬프트 포맷

```
Please complete the {func} function in the given Python code.

Relevant context:
```python
# 버전에 따라 sig+doc 또는 전체 코드
def some_dependency(x, y):
    """Does something."""
    ...
```

Input Code:
```python
def target_func(...):
    """..."""
```

Completed Code:
```

## 사용법

```bash
python build_prompt.py
```

## 입력 파일

- `DevEval/data.jsonl` — namespace, dependency, completion_path 등
- `DevEval/Source_Code/` — 실제 레포 소스
- `DevEval/Experiments/prompt/without_context/gpt-4-1106_prompt.jsonl` — 기존 프롬프트 (베이스)

## 디렉토리 구조

```
python_code_gen_test/
├── README.md
├── build_prompt.py          # 프롬프트 생성 스크립트
├── DevEval/                 # .gitignore — 직접 다운로드 필요
│   ├── data.jsonl
│   ├── Source_Code/
│   └── Experiments/prompt/
└── output/
    ├── prompt_sig_doc.jsonl
    └── prompt_full_body.jsonl
```
