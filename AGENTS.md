# AGENTS.md

## 역할

이 문서는 `python-khoa-api`에서 작업하는 Codex/agent를 위한 운영 가이드입니다. 작업 전에 먼저 이 파일을 읽고, 세부 API 목록은 `docs/openapi-catalog.md`, 테스트 규칙은 `docs/testing.md`, 사용자 예시는 `README.md`를 함께 확인합니다.

## 지시 우선순위

1. 사용자 요청
2. 이 `AGENTS.md`
3. `docs/openapi-catalog.md`
4. `docs/testing.md`
5. `README.md`
6. 기존 코드와 테스트
7. 최소한의 되돌릴 수 있는 가정

문서가 충돌하면 더 높은 우선순위의 문서를 따르고, 필요하면 낮은 우선순위 문서를 같은 변경 안에서 갱신합니다.

## 프로젝트 기준

- `python-khoa-api`는 국립해양조사원 KHOA 바다누리 ODMI OpenAPI의 비공식 Python 클라이언트입니다.
- Python import 패키지 이름은 `khoa`입니다.
- 대상 API는 data.go.kr을 통해 제공되는 KHOA ODMI 국가중점 OpenAPI입니다.
- 서비스 카탈로그의 기준 문서는 `docs/openapi-catalog.md`입니다.
- 범용 호출은 `KhoaClient.fetch()`가 담당하고, 안정적으로 모델링한 응답은 별도 typed helper와 Pydantic 모델로 제공합니다.
- Python 지원 기준은 `pyproject.toml`의 `requires-python`을 따릅니다.
- 기본 테스트는 실제 네트워크 호출 없이 동작해야 합니다.
- 실제 API 테스트는 `PYKHOA_RUN_LIVE=1`과 `KHOA_SERVICE_KEY`가 있을 때만 실행합니다.

## 구현 방향

- 불필요한 wrapper, adapter, facade, helper 계층을 만들지 않습니다. 기존 라이브러리나 표준 도구가 이미 해결한 동작은 가능한 한 `khoa`의 실제 호출 지점이나 모델 변환 지점에 직접 반영합니다.
- 다른 라이브러리의 구현 방식이 이 프로젝트 문제를 더 정확하게 해결한다면 단순히 변경 범위를 작게 유지하는 것보다 그 구현 방식을 바로 적용하는 쪽을 우선합니다.
- 외부 라이브러리의 구현을 참고하거나 가져올 때는 라이선스, 출처, 의존성 호환성을 먼저 확인하고, 새 public API나 동작 변경이 생기면 문서와 테스트를 함께 갱신합니다.

## 문서 구성

- `README.md`: 사용자용 개요, 설치, 예제, 테스트 안내.
- `docs/openapi-catalog.md`: KHOA ODMI 서비스 목록, `api_id`, data.go.kr ID, 필수 파라미터.
- `docs/testing.md`: 로컬 검증, live test 실행 방법, data.go.kr 403 처리 안내.
- `docs/repeated-mistakes.md`: 이 저장소에서 반복하지 말아야 할 작업 실수와 환경 함정.
- `pyproject.toml`: 패키징, 의존성, lint, test, type-check 설정.
- `src/khoa/client.py`: 사용자 진입점, 범용 호출, 페이지 처리, typed helper.
- `src/khoa/_http.py`: HTTP transport, retry, 상태 코드와 XML 오류 매핑.
- `src/khoa/_convert.py`: 문자열, 날짜, 숫자, CSV 파라미터 변환.
- `src/khoa/services.py`: KHOA ODMI 서비스 카탈로그.
- `src/khoa/models.py`: 사용자에게 반환하는 Pydantic 모델.
- `src/khoa/exceptions.py`: 예외 계층.
- `tests/`: 네트워크 없는 단위 테스트와 opt-in live test.

## 반드시 지킬 것

- 실제 `serviceKey`, API 키, 인증 토큰을 코드, fixture, 문서, 커밋, 로그에 남기지 않습니다.
- 기본 테스트에서 실제 data.go.kr 또는 KHOA 서버를 호출하지 않습니다.
- data.go.kr는 HTTP 200으로도 body-level 오류를 줄 수 있으므로 header/result code를 반드시 확인합니다.
- KHOA 응답의 `items.item`은 단일 dict 또는 list일 수 있으므로 항상 정규화합니다.
- 선행 0이 의미 있는 코드와 관측소 식별자는 `int`로 변환하지 않습니다.
- 문서의 파일 위치 정보는 프로젝트 루트 기준 상대 경로로 작성합니다. 예: `src/khoa/client.py`, `docs/testing.md`.
- 저장소 문서에는 로컬 절대 경로를 남기지 않습니다.
- Python 내부 문서와 유지보수용 설명은 한글로 작성합니다. 모듈, 클래스, 함수, 메서드 docstring과 설명 주석이 여기에 포함됩니다.
- 코드 식별자, API 파라미터, endpoint, enum 값, 외부 오류 메시지는 원문을 유지합니다.
- 새 public API, 모델, 예외, live test 정책을 추가하면 관련 문서도 같은 변경 안에서 갱신합니다.

## 로컬 도구와 인코딩

- 이 Windows 작업환경에서는 `rg.exe`가 `Access is denied`로 실패할 수 있습니다. 같은 실패를 반복하지 말고 PowerShell 파일 목록으로 우회합니다.
- 파일 목록은 `Get-ChildItem -Recurse -File -Name | Sort-Object` 또는 `git ls-files`를 사용합니다.
- 텍스트 검색은 `Select-String`을 사용합니다. 예: `Get-ChildItem -Recurse -File | Select-String -Pattern "KhoaClient"`.
- 한글 문서와 Python 파일은 UTF-8입니다. PowerShell에서 읽을 때 `Get-Content -Raw -Encoding UTF8` 또는 `Get-Content -Encoding UTF8`을 명시합니다.
- PowerShell 기본 출력에서 한글이 깨져 보이면 파일이 손상됐다고 판단하지 말고, 먼저 UTF-8 인코딩을 명시해 다시 확인합니다.

## 작업 소유권

### 클라이언트와 호출 흐름

담당 파일:

- `src/khoa/client.py`
- `src/khoa/_http.py`
- `src/khoa/_convert.py`

확인할 것:

- `serviceKey`, `pageNo`, `numOfRows`, `type=json` 요청 파라미터가 의도대로 구성되는지 테스트합니다.
- 응답 컨텍스트와 오류 메시지에 인증키가 노출되지 않아야 합니다.
- HTTP 상태 오류와 body-level API 오류를 typed exception으로 매핑합니다.
- required parameter 검증은 네트워크 호출 전에 수행합니다.

### 서비스 카탈로그

담당 파일:

- `src/khoa/services.py`
- `docs/openapi-catalog.md`

확인할 것:

- 서비스 key, `api_id`, data.go.kr ID, service path, operation이 서로 일치해야 합니다.
- 문서에 새 서비스나 필수 파라미터를 추가하면 `SERVICE_DEFINITIONS`도 함께 갱신합니다.
- KHOA 목록의 표시 건수와 실제 상세 링크 수가 다를 수 있으므로 실제 상세 페이지와 data.go.kr URL을 대조합니다.

### 모델

담당 파일:

- `src/khoa/models.py`

확인할 것:

- 안정적인 의미가 있는 public return 값은 Pydantic 모델로 제공합니다.
- 원본 응답은 `raw`에 보존하되 인증키는 저장하지 않습니다.
- 날짜와 시간은 가능한 한 KST timezone-aware 값으로 변환합니다.
- 코드 식별자와 API 원문 필드는 필요하면 문자열로 보존합니다.

### 테스트

담당 파일:

- `tests/conftest.py`
- `tests/test_client.py`
- `tests/test_http.py`
- `tests/test_services.py`
- `tests/test_live.py`
- `docs/testing.md`

확인할 것:

- 단위 테스트는 fake session으로 요청 URL, 파라미터, 응답 정규화를 검증합니다.
- live test는 `PYKHOA_RUN_LIVE=1`이 없으면 skip되어야 합니다.
- data.go.kr 403은 대개 해당 키가 KHOA ODMI 서비스 활용신청/승인을 받지 못한 상태입니다.
- live test 실패를 해결하려고 인증키를 코드나 fixture에 넣지 않습니다.

### 문서

담당 파일:

- 모든 `.md` 문서

확인할 것:

- 프로젝트 문서는 한글로 작성합니다.
- 파일 위치는 프로젝트 기준 상대 경로만 사용합니다.
- 명령어, URL, API 파라미터 이름, 코드 식별자는 원문을 유지합니다.
- 반복되는 실수는 `docs/repeated-mistakes.md`에 추가합니다.
- PowerShell 인코딩 문제와 `rg` 실행 권한 문제는 새 작업자도 볼 수 있게 이 문서와 `docs/repeated-mistakes.md`에 유지합니다.

## 검증

기본 검증:

```bash
python -m compileall src/khoa tests
python -m pytest
python -m ruff check .
python -m mypy src/khoa
```

실제 API 검증:

```bash
PYKHOA_RUN_LIVE=1 KHOA_SERVICE_KEY=<approved service key> python -m pytest -m live
```

실제 API 키는 환경변수로만 전달합니다. 명령 기록, 문서, 커밋 메시지에 키를 남기지 않습니다.

## 반복 실수 방지

- `rg`가 막힌 환경에서 같은 명령을 반복하지 않습니다. 바로 PowerShell 파일 목록과 `Select-String`으로 전환합니다.
- UTF-8 문서를 PowerShell 기본 출력으로 읽고 깨진 한글을 파일 손상으로 오판하지 않습니다.
- 문서에 `F:\...` 같은 로컬 절대 경로를 저장하지 않습니다.
- Python docstring을 영어로 새로 쓰지 않습니다. 내부 설명은 한글, 코드/API 식별자는 원문 유지가 기준입니다.
- 검증된 외부 구현을 활용할 수 있는데도 불필요한 wrapper 계층을 새로 만들지 않습니다. 최소 수정에 갇히기보다 실제 문제를 해결하는 구현을 직접 반영합니다.
- live test 실패 원인을 단위 테스트 실패처럼 처리하지 않습니다. 권한/승인 상태와 네트워크 상태를 분리해서 기록합니다.
