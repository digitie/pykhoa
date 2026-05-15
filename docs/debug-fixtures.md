# 디버그 실행과 fixture replay

`python-khoa-api`는 Streamlit 같은 Web UI 프레임워크에 직접 의존하지 않습니다.
대신 별도 디버그 UI 패키지에서 가져다 쓸 수 있는 공통 구성요소만 제공합니다.

- `KhoaClient.debug_fetch()`: API 입력, 요청, 응답, 파싱 결과, 가공 결과, trace를
  `DebugRun`으로 반환합니다.
- `jsonable()`: Pydantic v2 모델을 `model_dump(mode="json")` 기준으로 JSON 저장
  가능한 값으로 변환합니다.
- `redact_sensitive()`: `serviceKey`, `api_key`, `Authorization`, token 값을
  fixture 저장 전에 `<REDACTED>`로 바꿉니다.
- `save_fixture()`: `tests/fixtures/{function}/{case}.json` 형태의 replay fixture를
  저장합니다. 같은 파일이 있으면 기본적으로 덮어쓰지 않습니다.
- `tests/test_generated_fixtures.py`: `tests/fixtures/**/*.json` 파일을 자동으로
  읽어 외부 API 호출 없이 parser/processor replay 테스트를 실행합니다.

## DebugRun

```python
from khoa import KhoaClient

client = KhoaClient(api_key="...")
run = client.debug_fetch(
    "roms",
    ymin=34.0,
    ymax=34.1,
    xmin=123.2,
    xmax=123.3,
)

print(run.input)
print(run.request)
print(run.response)
print(run.parsed)
print(run.processed)
print(run.trace)
print(run.error)
print(run.catalog)
```

성공 시 `parsed`에는 `Page[RawRecord]`, `processed`에는 정규화된 item tuple이
들어갑니다. 오류가 나면 예외를 밖으로 던지지 않고 `error`에 오류 타입, endpoint,
status code, result code, 재시도 가능 여부를 담습니다.

`catalog`에는 Streamlit의 debug trace 탭에서 표로 보여주기 쉬운 API 카탈로그 항목이
들어갑니다. 주요 필드는 아래와 같습니다.

- `dataset_name`: 사람이 읽을 수 있는 데이터셋명. 예: `ROMS 수치예측모델`
- `dataset_label`: 데이터셋명과 라이브러리 service key를 함께 보여주는 라벨
- `service_key_url`: data.go.kr에서 서비스키 활용신청/상세 확인을 할 수 있는 링크
- `data_source`, `service_key_env_names`: 데이터소스별 서비스키 로딩에 쓰는 정보
- `endpoint`, `required_params`, `optional_params`, `response_fields`

Streamlit에서는 예를 들어 아래처럼 표시할 수 있습니다.

```python
import pandas as pd
import streamlit as st

trace_tab, catalog_tab = st.tabs(["Debug Trace", "Catalog"])
with trace_tab:
    st.write(run.trace)

with catalog_tab:
    st.dataframe(pd.json_normalize([run.catalog], sep="."))
    if run.catalog:
        st.link_button("서비스키 받기", run.catalog["service_key_url"])
```

## Fixture 저장

```python
from khoa import save_fixture

path = save_fixture(
    base_dir="tests/fixtures",
    function_name="roms",
    case_name="roms_basic",
    description="ROMS 기본 응답 replay",
    input_data=run.input,
    request_data=run.request,
    response_data=run.response,
    parsed_result=run.parsed,
    processed_result=run.processed,
    assertion={
        "mode": "snapshot",
        "exclude_fields": ["fetched_at", "request_id", "updated_at"],
        "required_fields": [],
    },
    library_version="0.1.0",
)
print(path)
```

저장 전에는 `jsonable()`과 `redact_sensitive()`가 적용됩니다. API key, token,
인증 header는 fixture에 원문으로 남기지 않습니다.

## Fixture 포맷

```json
{
  "name": "roms_basic",
  "function": "roms",
  "description": "ROMS 기본 응답 replay",
  "input": {},
  "request": {
    "method": "GET",
    "url": "https://apis.data.go.kr/1192000/service/OceansData/roms/GetRomsApiService",
    "query": {},
    "headers": {
      "Accept": "application/json"
    }
  },
  "response": {
    "status_code": 200,
    "headers": {
      "content-type": "application/json"
    },
    "body": {}
  },
  "parsed": {},
  "processed": {},
  "assertion": {
    "mode": "snapshot",
    "exclude_fields": [],
    "required_fields": []
  },
  "meta": {
    "created_at": "2026-05-15T20:30:00+09:00",
    "library_version": "0.1.0",
    "source": "debug_ui"
  }
}
```

`response.body`에는 외부 API 원문 응답 중 parser에 다시 넣을 수 있는 body를
저장합니다. 기본 테스트는 이 값을 이용해 외부 API를 다시 호출하지 않고 replay만
수행합니다.

## Assertion mode

현재 공통 runner는 아래 모드를 지원합니다.

- `snapshot`: `processed` 전체 비교. `exclude_fields`는 재귀적으로 제외합니다.
- `schema_only`: parse/process 성공 여부만 확인합니다.
- `required_fields`: `actual` 최상위 dict에 특정 필드가 있는지 확인합니다.
- `count`: `actual.count`와 `expected.count`를 비교합니다.

새 fixture function을 추가할 때는 `tests/runners.py`의 `RUNNERS`에 parse/process
함수를 등록합니다. fixture마다 별도 테스트 파일을 만들지 않습니다.

## Web UI와의 경계

Web UI를 만들 때는 별도 프로젝트에서 `python-khoa-api`를 wheel 또는 editable로
설치해 import합니다.

```bash
pip install -e ../python-khoa-api
streamlit run app.py
```

Streamlit 의존성, preset/history 저장소, diff UI, report export는 Web UI
프로젝트에 둡니다. 이 라이브러리는 `DebugRun` 생성과 fixture 저장, replay 테스트
계약만 담당합니다.

저장소의 `examples/streamlit_debug_ui.py`는 최소 예제 앱입니다. API를 선택하면
`dataset_label`로 데이터셋명을 보여주고, sidebar와 Debug Trace 탭에
`service_key_url` 기반의 서비스키 신청 링크를 표시합니다.

서비스키 입력칸을 비워두면 예제 앱은 `data_source`에 맞춰 환경변수와 로컬 `.env`에서
키를 읽습니다. data.go.kr 서비스는 `KHOA_DATA_GO_KR_SERVICE_KEY`, KHOA 직접 endpoint는
`KHOA_DIRECT_SERVICE_KEY`를 우선 사용합니다.
