# python-khoa-api

data.go.kr로 제공되는 국립해양조사원 KHOA 바다누리 ODMI OpenAPI의 비공식
Python 클라이언트입니다.

내장 서비스 카탈로그는 KHOA ODMI OpenAPI 목록을 기준으로 합니다.
배포 패키지 이름은 `python-khoa-api`이고, 코드에서는 `khoa`로 import합니다.

<https://www.khoa.go.kr/oceandata/openapi/odmi/odmiApiList.do>

## 설치

```bash
pip install -e .
```

## 빠른 시작

```python
from khoa import KhoaClient

client = KhoaClient(api_key="...")  # 또는 KhoaClient()

page = client.fetch(
    "roms",
    ymin=34.0,
    ymax=34.1,
    xmin=123.2,
    xmax=123.3,
    num_of_rows=10,
)

for row in page.items:
    print(row["predcDt"], row["lat"], row["lot"], row["wtem"])
```

`fetch()`는 `khoa.SERVICE_DEFINITIONS`의 서비스 key, KHOA `api_id`,
operation 이름, 한글 제목을 모두 받을 수 있습니다.

명시 키를 넘기지 않으면 환경변수와 현재 작업 디렉토리의 `.env`에서 데이터소스별
서비스키를 찾습니다. 복사/붙여넣기로 들어간 앞뒤 공백, 줄바꿈, 중간 공백은
자동으로 제거합니다.

```env
KHOA_DATA_GO_KR_SERVICE_KEY=...
KHOA_DIRECT_SERVICE_KEY=...
VWORLD_API_KEY=...
```

`KHOA_DATA_GO_KR_SERVICE_KEY`는 data.go.kr ODMI 호출에 쓰고,
`KHOA_DIRECT_SERVICE_KEY`는 `beach_search()` 같은 KHOA 직접 endpoint에 씁니다.

자주 쓰는 KHOA 파라미터는 snake-case 별칭도 받을 수 있습니다.

```python
page = client.fetch("dt_recent", obs_code="DT_0001", req_date="20260507")
```

ROMS 행은 typed helper로도 받을 수 있습니다.

```python
page = client.roms(ymin=34.0, ymax=34.1, xmin=123.2, xmax=123.3)
prediction = page.items[0]
print(prediction.predicted_at, prediction.water_temperature_c)
```

모든 서비스 key는 동적 편의 메서드로도 호출할 수 있습니다.

```python
page = client.rip_current(beach_code="BCH001", req_date="20260507")
```

`beach_index()`는 해수욕지수 원문 행을 해수욕장별 DTO로 묶어 반환합니다.
장소 하나가 여러 예보 슬롯을 `forecasts`에 담고, VWorld 역지오코딩 주소 필드는
선택적으로 붙일 수 있습니다. `python-vworld-api`의 `vworld` 패키지가 설치되어
있고 `VWORLD_API_KEY`가 환경변수나 `.env` 파일에 있어야 합니다.

```python
page = client.beach_index(num_of_rows=3)
address_page = client.beach_index(
    num_of_rows=3,
    include_address=True,
    vworld_env_file=".env",
)

place = address_page.items[0]
print(place.name, place.parcel_address, place.road_address)
for forecast in place.forecasts:
    print(forecast.predicted_on, forecast.forecast_period, forecast.open_status)
```

KHOA 직접 endpoint인 `https://khoa.go.kr/oceandata/api/beach/search.do`는
`beach_search()`로 호출합니다. 이 endpoint는 data.go.kr ODMI 키가 아니라 KHOA
직접 `ServiceKey`를 요구할 수 있으므로 필요하면 `service_key=`로 별도 키를 넘깁니다.
결과는 해수욕장 단위 `BeachSearchResult` DTO이며, 번들 해수욕장 목록의 좌표/주소가
가능한 경우 함께 붙습니다.

```python
result = client.beach_search("BCH001", service_key="...")
print(result.name, result.parcel_address)
for observation in result.observations:
    print(observation.observed_at, observation.water_temperature_c)
```

해수욕지수 외의 주요 해양 레저 지수도 장소별 DTO로 묶어 반환합니다. 같은 장소의
여러 예보 행은 `MarineIndexPlace.forecasts`에 들어가며, `include_address=True`와
VWorld 설정을 넘기면 원 좌표와 가까운 보정 좌표를 확인해 주소를 보강합니다.

```python
surfing = client.surfing_index(
    num_of_rows=20,
    include_address=True,
    vworld_env_file=".env",
)

place = surfing.items[0]
print(place.service_key, place.name, place.parcel_address)
for forecast in place.forecasts:
    print(forecast.predicted_on, forecast.total_index, forecast.metrics)
```

DTO 그룹핑 helper가 제공되는 지수는 `sea_split_index`, `fishing_index`,
`seasickness_index`, `skin_scuba_index`, `mudflat_index`, `surfing_index`,
`sea_trip_index`입니다.

## 디버그 fixture

별도 Web UI나 로컬 디버그 스크립트에서 fixture를 만들 수 있도록 Streamlit에
의존하지 않는 디버그 도구를 제공합니다.

```python
from khoa import KhoaClient, save_fixture

client = KhoaClient(api_key="...")
run = client.debug_fetch(
    "roms",
    ymin=34.0,
    ymax=34.1,
    xmin=123.2,
    xmax=123.3,
)

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
)
print(path)
```

fixture 저장 전 `serviceKey`, `api_key`, `Authorization`, token 값은 자동으로
마스킹됩니다. 저장된 `tests/fixtures/**/*.json`은 기본 pytest에서 외부 API 호출 없이
replay 방식으로 검증됩니다. 자세한 내용은 `docs/debug-fixtures.md`를 참고합니다.

API 선택 UI가 필요하면 `get_api_catalog()` 또는 `client.api_catalog()`를 사용합니다.
각 항목에는 사람이 읽을 수 있는 `dataset_name`, 표시용 `dataset_label`, data.go.kr
서비스키 신청/상세 링크인 `service_key_url`, 데이터소스별 키 후보인
`service_key_env_names`가 들어 있습니다.

```python
from khoa import get_api_catalog

for item in get_api_catalog():
    print(item["dataset_label"], item["service_key_url"])
```

## KHOA 포털 관측소 목록

일부 KHOA 포털 상세 페이지는 data.go.kr ODMI 게이트웨이가 아니라 별도 AJAX
엔드포인트로 관측소 목록을 제공합니다.

<https://www.khoa.go.kr/oceandata/openapi/getOpenApiInfo.do>

`khoa`는 이 엔드포인트를 감싸고, OpenAPI 상세 id `36`의 "해수욕장 정보"
관측소 356개를 번들로 제공합니다. KHOA 페이지의 수정 주기는 `상시`이며,
라이브러리에서는 운영상 30분 주기 자료로 취급합니다.

번들 해수욕장 목록에는 `python-vworld-api`의 VWorld 역지오코딩으로 얻은 주소 정보도
함께 들어 있습니다. 좌표가 해상이나 백사장 위에 있어 원 좌표에서 주소가
나오지 않는 경우에는 가까운 주변 좌표를 순차 확인합니다. `road_address_code`는
26자리 도로명주소 관리코드이며, 12자리 도로명코드는 `road_name_code`로
별도 제공합니다. VWorld에서 도로명 주소가 반환되지 않는 지점은
`road_address_code`, `road_name_code`, `road_address`가 `None`일 수 있습니다.
좌표 필드는 `kraddr.base.PlaceCoordinate`, 주소 필드는 `kraddr.base.Address`를 직접 사용합니다.

```python
from khoa import (
    BEACH_INFO_UPDATE_INTERVAL_MINUTES,
    BEACH_OBSERVATORIES,
    fetch_observatory_list,
    get_beach_observatories,
)

print(BEACH_INFO_UPDATE_INTERVAL_MINUTES)  # 30
print(len(BEACH_OBSERVATORIES))  # 356, 네트워크 호출 없음

beach = get_beach_observatories()[0]
print(beach.coordinate.lat, beach.coordinate.lon)
print(beach.address.display_address if beach.address else None)
print(beach.legal_dong_code, beach.road_address_code, beach.detail_address)

live = fetch_observatory_list("36")  # KHOA 포털 AJAX 엔드포인트로 POST
```

라이브 포털 목록에도 주소를 붙여야 하면 `vworld` 클라이언트를 넘깁니다.

```python
from vworld import VworldClient
from khoa import fetch_observatory_list

vworld = VworldClient.from_env()
live = fetch_observatory_list("36", include_address=True, vworld_client=vworld)
```

## 카탈로그

```python
from khoa import SERVICE_DEFINITIONS

for service in SERVICE_DEFINITIONS:
    print(service.key, service.title, service.required_params, service.requested_url)
```

현재 카탈로그에는 KHOA가 공개한 국가중점 ODMI 서비스 상세 페이지 46개가
들어 있습니다. ROMS, 해양레저지수, 바다안개, 조위/조류 관측과 예측,
TideBED, 이안류, 선박운항지수, 해황예보도 서비스를 포함합니다.

## 테스트

```bash
python -m compileall src/khoa tests
python -m pytest
python -m ruff check .
python -m mypy src/khoa
```

live test는 실제 data.go.kr KHOA ODMI 서비스를 호출하므로 승인된 키가
필요합니다.

```bash
PYKHOA_RUN_LIVE=1 KHOA_SERVICE_KEY=... python -m pytest -m live
```

data.go.kr가 HTTP 403을 반환하면 게이트웨이에는 도달했지만 해당 KHOA ODMI
서비스 활용 권한이 없는 상태일 가능성이 큽니다. data.go.kr에서 대상 서비스
활용신청/승인을 받은 뒤 다시 실행합니다.
