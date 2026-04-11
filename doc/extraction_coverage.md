# AST Extraction Coverage

## Summary

- **data_filtered.jsonl**: 1,323 samples (dependency가 있는 것만)
- **context 추출 성공**: 1,322 / 1,323
- **context 추출 실패**: 1건

## Dependency Symbol 추출 통계 (총 4,448건)

### Symbol Resolution (`resolve_symbol_file`)

| 단계 | 건수 | 비율 |
|---|---|---|
| 직접 경로 매칭 | 3,954 | 88.9% |
| `src/` 접두사 매칭 | 489 | 11.0% |
| fallback (os.walk) | 5 | 0.1% |

- remainder 있음 (구체 심볼): 4,295건
- remainder 없음 (모듈 참조): 153건

### AST Symbol 추출 (remainder 있는 4,295건)

| 심볼 종류 | 건수 | 비율 |
|---|---|---|
| 함수 | 821 | 19.1% |
| 클래스 전체 | 534 | 12.4% |
| 클래스 메서드 | 1,103 | 25.7% |
| 클래스 속성 (assign) | 191 | 4.4% |
| 클래스 속성 (ann_assign) | 63 | 1.5% |
| 클래스 속성 (self.xxx) | 935 | 21.8% |
| 모듈 변수 | 417 | 9.7% |
| **추출 실패** | **18** | **0.4%** |

추출 실패 18건은 stdlib 반환값 속성(`urlparse.netloc`), C extension 상수, lazy import 등 AST 정적 분석의 한계.
LLM이 이미 알고 있는 정보(stdlib 등)이므로 context로 줄 필요 없음.

## 실패 1건 상세

```
namespace: faker.decode.unidecode
dependency: {"cross_file": ["faker.decode.codes"]}
```

- `faker.decode.codes`는 모듈이 아니라 **변수** (`codes`라는 dict)
- `from .codes import codes`로 import 후 `codes[codepoint]`으로 직접 사용
- 모듈 참조 경로(`module.attr` 패턴)로 처리되는데, `codes.X` 형태 접근이 아니라 인덱싱이므로 `find_used_attrs_on_module`이 빈 결과 반환
- 원인: symbol resolution에서 `faker/decode/codes.py` 파일로 해석되어 remainder가 빈 문자열이 됨. 실제로는 파일이 아니라 그 파일 안의 `codes` 변수를 가리키는 것
