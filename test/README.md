# build_prompt 검증 테스트

`build_prompt.py`의 `build_context_string`이 손으로 만든 정답지와 일치하는지 pytest로 검증.

## 구조

```
test/
├── conftest.py              # pytest fixtures + helpers
├── test_build_prompt.py     # 테스트 케이스 (parametrize)
└── ground_truth/
    ├── 0061_darwin_installer/
    │   ├── meta.json        # namespace, deps 정보
    │   ├── sd_sd.py         # sig_doc/sig_doc 모드 정답 context
    │   └── full_full.py     # full/full 모드 정답 context
    ├── 0280_compute_hashes_from_fileobj/
    │   ├── meta.json
    │   ├── sd_sd.py
    │   └── full_full.py
    └── ... (총 9개 샘플)
```

## 실행

프로젝트 루트에서:

```bash
cd /home/ihkang/ttt/pycodegen
pytest test/ -v
```

또는 `test/` 안에서:

```bash
cd test/
pytest -v
```

## 케이스 추가

새 샘플 정답지 추가하려면:

1. `ground_truth/<line>_<short_name>/` 폴더 생성
2. `meta.json` — `namespace` 필드 필수
3. `sd_sd.py` — `func_mode=sig_doc, class_mode=sig_doc` 정답 context
4. `full_full.py` — `func_mode=full, class_mode=full` 정답 context

자동으로 테스트 picked-up 됨.

## 비교 방식

- 줄 단위 trailing whitespace 제거
- 빈 trailing 줄 제거
- 그 외는 **정확히 일치**해야 통과

## 현재 상태

테스트는 **실패하는 게 정상** — `build_prompt.py`가 아직 leak/duplicate 버그 가지고 있어서.
이 테스트가 **수정 후 통과해야** 진짜 고쳐진 것.
