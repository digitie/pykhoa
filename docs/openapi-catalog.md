# KHOA ODMI OpenAPI 카탈로그

출처: <https://www.khoa.go.kr/oceandata/openapi/odmi/odmiApiList.do>

KHOA 페이지에서 실제 확인되는 국가중점 ODMI 상세 페이지는 46개입니다. 사이트
문구에는 54건으로 표시되지만 6페이지가 비어 있고, 상세 페이지의 data.go.kr
매핑도 아래 46개 항목을 기준으로 확인했습니다.

| key | api_id | data.go.kr | title | required |
| --- | --- | --- | --- | --- |
| `roms` | `SV_AP_01_001` | `15142227` | ROMS 수치예측모델 | `ymin`, `ymax`, `xmin`, `xmax` |
| `beach_index` | `SV_AP_01_002` | `15142484` | 해수욕지수 |  |
| `sea_split_index` | `SV_AP_01_003` | `15142485` | 바다갈라짐 체험지수 |  |
| `fishing_index` | `SV_AP_01_004` | `15142486` | 바다낚시지수 | `gubun` |
| `seasickness_index` | `SV_AP_01_005` | `15142487` | 뱃멀미지수 |  |
| `skin_scuba_index` | `SV_AP_01_006` | `15142488` | 스킨스쿠버지수 |  |
| `mudflat_index` | `SV_AP_01_007` | `15142489` | 갯벌체험지수 |  |
| `surfing_index` | `SV_AP_01_008` | `15142490` | 서핑지수 |  |
| `sea_trip_index` | `SV_AP_01_009` | `15142491` | 바다여행지수 |  |
| `waterlogged` | `SV_AP_01_010` | `15142492` | 연안 침수 정보 | `sggCd` |
| `climate_sea_level` | `SV_AP_01_011` | `15142493` | 지역 해양기후 수치모델 기반 미래 해수면 상승 전망 | `ymin`, `ymax`, `xmin`, `xmax` |
| `climate_salinity` | `SV_AP_01_012` | `15142494` | 지역 해양기후 수치모델 기반 미래 표층염분 상승 전망 | `ymin`, `ymax`, `xmin`, `xmax` |
| `climate_water_temperature` | `SV_AP_01_013` | `15142495` | 지역 해양기후 수치모델 기반 미래 표층수온 상승 전망 | `ymin`, `ymax`, `xmin`, `xmax` |
| `climate_current` | `SV_AP_01_014` | `15142496` | 지역 해양기후 수치모델 기반 미래 해수유동 변동 전망 | `ymin`, `ymax`, `xmin`, `xmax` |
| `water_depth` | `SV_AP_01_015` | `15142498` | 자연과학용 수심정보 | `ymin`, `ymax`, `xmin`, `xmax` |
| `seafog_appear` | `SV_AP_02_001` | `15142269` | 해무 발생·소산정보 | `obsCode` |
| `seafog_cctv` | `SV_AP_02_002` | `15142499` | 해무 CCTV 스틸컷 |  |
| `seafog_range` | `SV_AP_02_003` | `15142501` | 해무 판별정보 | `obsCode` |
| `sailing_index` | `SV_AP_02_004` | `15142502` | 항만해양지수 | `obsName` |
| `real_time_sea_current` | `SV_AP_02_005` | `15142503` | 준실시간 해류도 | `sea` |
| `avg_sea_current` | `SV_AP_02_006` | `15142504` | 평균 해류도 | `sea` |
| `vortex` | `SV_AP_02_007` | `15142505` | 소용돌이 |  |
| `survey_water_temp` | `SV_AP_02_008` | `15142506` | 조위관측소 실측 수온 | `obsCode` |
| `survey_tide_level` | `SV_AP_02_009` | `15142507` | 조위관측소 실측·예측 조위 | `obsCode` |
| `survey_air_temp` | `SV_AP_02_010` | `15142508` | 조위관측소 실측 기온 | `obsCode` |
| `survey_air_press` | `SV_AP_02_011` | `15142509` | 조위관측소 실측 기압 | `obsCode` |
| `survey_wind` | `SV_AP_02_012` | `15142518` | 조위관측소 실측 풍향/풍속 | `obsCode` |
| `survey_seafog` | `SV_AP_02_013` | `15142519` | 해무관측소 최신 관측 데이터 | `obsCode` |
| `dt_recent` | `SV_AP_03_001` | `15155508` | 조위관측소 최신 관측데이터 | `obsCode` |
| `tw_recent` | `SV_AP_03_002` | `15155516` | 해양관측부이 최신 관측데이터 | `obsCode` |
| `hf_current` | `SV_AP_03_003` | `15155531` | 해수유동 관측소 실측 유향·유속 | `obsCode` |
| `noon_wave` | `SV_AP_03_004` | `15155994` | 국가해양관측망 실측 파랑 | `obsCode` |
| `ls_term_tide_obs` | `SV_AP_03_005` | `15156002` | 장단기 조석관측 | `obsCode` |
| `noon_monthly_obs` | `SV_AP_04_001` | `15156005` | 국가해양관측망 월간 관측자료(QC) | `obsCode` |
| `deviation_cal` | `SV_AP_04_002` | `15156011` | 편차계산표(조석성과) | `obsCode` |
| `extreme_tide_level` | `SV_AP_04_003` | `15156013` | 최극조위(조석성과) | `obsCode` |
| `mean_sea_level` | `SV_AP_04_004` | `15156015` | 평균해면성과표(조석성과) | `obsCode` |
| `hourly_tide` | `SV_AP_04_005` | `15156017` | 1시간 조위(조석성과) | `obsCode` |
| `tide_forecast_high_low` | `SV_AP_04_006` | `15156018` | 조석예보(고, 저조) | `obsCode` |
| `tide_forecast_time` | `SV_AP_04_007` | `15156022` | 조석예보(시계열) | `obsCode` |
| `current_forecast_time` | `SV_AP_04_008` | `15156024` | 조류예보(시계열) | `obsCode` |
| `current_forecast_flood_ebb` | `SV_AP_04_009` | `15156025` | 조류예보 최강창낙조 및 전류 | `obsCode` |
| `tidebed` | `SV_AP_04_010` | `15156026` | TideBED 예측 조위(1분) | `lot`, `lat` |
| `rip_current` | `SV_AP_04_011` | `15156028` | 이안류 지수 | `beachCode` |
| `ship_index` | `SV_AP_04_012` | `15156036` | 선박운항지수 | `category` |
| `ocean_condition` | `SV_AP_04_013` | `15156040` | 해황예보도 | `areaCode` |

## 비표준 포털 관측소 엔드포인트

KHOA 포털 상세 페이지는 관측소 목록을 아래 AJAX 엔드포인트로 제공합니다.

<https://www.khoa.go.kr/oceandata/openapi/getOpenApiInfo.do>

요청은 form field `id`를 넣은 `POST`입니다. OpenAPI 상세 id `36`
(`해수욕장 정보`)의 응답에는 `observatoryList` 행이 들어 있으며, 원문 필드는
아래와 같습니다.

- `id`: 해수욕장/관측소 코드. 예: `BCH001`
- `name`: 한글 해수욕장 이름. 예: `해운대해수욕장`
- `data_type`: `BEACH`
- `lat`: WGS84 위도
- `lon`: WGS84 경도

`khoa`의 해수욕장 번들 목록은 위 원문 필드에 VWorld 역지오코딩 주소
필드를 추가로 포함합니다.

- `coordinate`: `pykrtour.PlaceCoordinate` 타입의 WGS84 좌표
- `address`: `pykrtour.Address` 타입의 주소. 지번주소, 도로명주소, 상세주소,
  우편번호, 주소 코드 값을 직접 포함합니다.
- `legal_dong_code`: `address`에서 파생한 법정동코드 호환 속성
- `road_address_code`: `address`에서 파생한 26자리 도로명주소 관리코드 호환 속성.
  구성은 행정구역 8자리,
  도로명코드 7자리, 건물 위치 구분 1자리, 건물 본번 5자리, 건물 부번 5자리입니다.
  VWorld가 도로명 결과를 주지 않는 지점은 `None`일 수 있습니다.
- `road_name_code`: `address`에서 파생한 12자리 도로명코드. 행정구역 시군구 5자리와 도로명코드
  7자리를 결합한 값입니다.
- `parcel_address`: `address`에서 파생한 지번 주소 호환 속성
- `road_address`: `address`에서 파생한 도로명 주소 호환 속성
- `detail_address`: `address.detail_address`에서 파생한 VWorld `structure.detail` 상세주소 호환 속성
- `zipcode`: `address`에서 파생한 우편번호 호환 속성
- `address_coordinate`: `pykrtour.PlaceCoordinate` 타입의 주소 조회 좌표
- `address_distance_m`: 원 KHOA 좌표와 주소 조회 좌표 사이 거리
- `address_match_type`: 원 좌표면 `exact`, 주변 좌표면 `nearby`
- `address_source`: `vworld`

2026-05-10 확인 기준:

- 상세 id: `36`
- 제목: `해수욕장 정보`
- KHOA 페이지 수정 주기: `상시`
- 이 라이브러리에서 사용하는 운영상 갱신 주기: 30분
- 번들 관측소 수: 356
- 주소 보강 방식: `pyvworld` VWorld 역지오코딩, 원 좌표 실패 시 주변 좌표 순차 확인
- 번들 payload SHA-256: `9b64b14215052a79ae5736b4f13ae9733e520e5e410055b10e28b91506ceb3c7`

번들 목록은 `khoa.BEACH_OBSERVATORIES` 또는
`khoa.get_beach_observatories()`로 사용합니다. 포털 엔드포인트에서 새로
가져오려면 `khoa.fetch_observatory_list("36")`을 호출하고, live 결과에도
주소를 붙이려면 `include_address=True`와 `pyvworld` 클라이언트를 전달합니다.
