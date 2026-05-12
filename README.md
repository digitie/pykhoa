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

client = KhoaClient(api_key="...")  # 또는 KhoaClient.from_env()

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

## KHOA 포털 관측소 목록

일부 KHOA 포털 상세 페이지는 data.go.kr ODMI 게이트웨이가 아니라 별도 AJAX
엔드포인트로 관측소 목록을 제공합니다.

<https://www.khoa.go.kr/oceandata/openapi/getOpenApiInfo.do>

`khoa`는 이 엔드포인트를 감싸고, OpenAPI 상세 id `36`의 "해수욕장 정보"
관측소 356개를 번들로 제공합니다. KHOA 페이지의 수정 주기는 `상시`이며,
라이브러리에서는 운영상 30분 주기 자료로 취급합니다.

번들 해수욕장 목록에는 `pyvworld`의 VWorld 역지오코딩으로 얻은 주소 정보도
함께 들어 있습니다. 좌표가 해상이나 백사장 위에 있어 원 좌표에서 주소가
나오지 않는 경우에는 가까운 주변 좌표를 순차 확인합니다. `road_address_code`는
26자리 도로명주소 관리코드이며, 12자리 도로명코드는 `road_name_code`로
별도 제공합니다. VWorld에서 도로명 주소가 반환되지 않는 지점은
`road_address_code`, `road_name_code`, `road_address`가 `None`일 수 있습니다.
좌표 필드는 `pykrtour.PlaceCoordinate`, 주소 필드는 `pykrtour.Address`를 직접 사용합니다.

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

라이브 포털 목록에도 주소를 붙여야 하면 `pyvworld` 클라이언트를 넘깁니다.

```python
from pyvworld import VworldClient
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
