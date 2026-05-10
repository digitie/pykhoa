# 반복 실수 방지

이 문서는 `pykhoa` 작업 중 반복되기 쉬운 실수를 줄이기 위한 체크리스트입니다.

## 로컬 도구

- 이 환경에서는 `rg.exe`가 `Access is denied`로 실패할 수 있습니다.
- `rg` 실패를 반복하지 말고 `Get-ChildItem -Recurse -File -Name | Sort-Object`, `git ls-files`, `Select-String`으로 우회합니다.
- 예시:

```powershell
Get-ChildItem -Recurse -File -Name | Sort-Object
Get-ChildItem -Recurse -File | Select-String -Pattern "KhoaClient"
```

## 인코딩

- 문서와 Python 소스는 UTF-8로 작성합니다.
- PowerShell 기본 출력에서 한글이 깨져 보일 수 있습니다.
- 깨진 출력만 보고 파일 내용이 손상됐다고 판단하지 말고 UTF-8을 명시해서 다시 읽습니다.

```powershell
Get-Content -Path AGENTS.md -Raw -Encoding UTF8
Get-Content -Path docs/testing.md -Raw -Encoding UTF8
```

## 문서 경로

- 문서의 파일 위치 정보는 프로젝트 루트 기준 상대 경로로 작성합니다.
- 좋은 예: `pykhoa/client.py`, `docs/openapi-catalog.md`, `tests/test_live.py`
- 나쁜 예: 로컬 사용자 환경에 묶인 절대 경로

## Python 내부 문서

- Python 내부 문서와 유지보수용 설명은 한글로 작성합니다.
- 대상은 모듈 docstring, 클래스 docstring, 함수와 메서드 docstring, 설명 주석입니다.
- 코드 식별자, API 파라미터명, endpoint, 외부 오류 메시지는 원문을 유지합니다.

## 구현 방식

- 불필요한 wrapper, adapter, facade, helper 계층을 새로 만들지 않습니다.
- 다른 라이브러리에서 이미 검증된 구현 방식이 있으면 최소 수정에만 맞추려고 우회하지 말고, 라이선스와 의존성 호환성을 확인한 뒤 프로젝트 코드에 직접 반영합니다.
- 외부 구현을 적용하면서 public API나 동작이 바뀌면 관련 문서와 테스트를 같은 변경 안에서 갱신합니다.

## API 키와 live test

- 실제 `serviceKey`는 코드, fixture, 문서, 커밋 메시지에 남기지 않습니다.
- live test는 `PYKHOA_RUN_LIVE=1`과 `KHOA_SERVICE_KEY`가 있을 때만 실행합니다.
- data.go.kr `HTTP 403`은 보통 키가 해당 KHOA ODMI 서비스 활용신청/승인을 받지 못했다는 뜻입니다.
- 403을 해결하려고 테스트 코드를 느슨하게 만들지 말고, 권한 상태를 확인합니다.

## 응답 형태

- KHOA/data.go.kr 응답의 `items.item`은 단일 dict 또는 list일 수 있습니다.
- 단일 item 응답을 list로 단정하지 말고 클라이언트 경계에서 정규화합니다.
- body-level `resultCode` 실패를 빈 성공 응답처럼 반환하지 않습니다.
