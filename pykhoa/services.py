"""KHOA ODMI service catalog.

The catalog is based on the KHOA Badanuri ODMI OpenAPI list and the matching
data.go.kr OpenAPI pages. KHOA currently exposes 46 국가중점 ODMI detail pages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DATA_GO_KR_PROVIDER_CODE: Final = "1192136"
DEFAULT_BASE_URL: Final = f"http://apis.data.go.kr/{DATA_GO_KR_PROVIDER_CODE}"
KHOA_ODMI_LIST_URL: Final = "https://www.khoa.go.kr/oceandata/openapi/odmi/odmiApiList.do"


@dataclass(frozen=True, slots=True)
class ServiceDefinition:
    """One KHOA ODMI OpenAPI operation."""

    key: str
    api_id: str
    data_go_kr_id: str
    title: str
    category: str
    service_path: str
    operation: str
    required_params: tuple[str, ...] = ()
    optional_params: tuple[str, ...] = ()
    response_fields: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    @property
    def endpoint(self) -> str:
        return f"{self.service_path}/{self.operation}"

    @property
    def requested_url(self) -> str:
        return f"{DEFAULT_BASE_URL}/{self.endpoint}"

    @property
    def data_go_kr_url(self) -> str:
        return f"https://www.data.go.kr/data/{self.data_go_kr_id}/openapi.do"

    @property
    def khoa_detail_url(self) -> str:
        return (
            "https://www.khoa.go.kr/oceandata/openapi/odmi/odmiApiDetail.do"
            f"?apiId={self.api_id}"
        )


def _category(api_id: str) -> str:
    group = api_id.split("_")[2]
    return {
        "01": "gis_ocean",
        "02": "marine_safety",
        "03": "ocean_observation",
        "04": "ocean_environment",
    }.get(group, "unknown")


_SERVICE_ROWS: Final[tuple[tuple[object, ...], ...]] = (
    (
        "roms",
        "SV_AP_01_001",
        "15142227",
        "ROMS 수치예측모델",
        "roms",
        "GetRomsApiService",
        ("ymin", "ymax", "xmin", "xmax"),
        ("include", "exclude"),
        ("predcDt", "lat", "lot", "crdir", "crsp", "wtem"),
    ),
    (
        "beach_index",
        "SV_AP_01_002",
        "15142484",
        "해수욕지수",
        "fcstBeachv2",
        "GetFcstBeachApiServicev2",
        (),
        ("placeCode", "reqDate", "include", "exclude"),
        (
            "bbchNm",
            "lat",
            "lot",
            "predcYmd",
            "predcNoonSeCd",
            "maxWvhgt",
            "avgWtem",
            "avgArtmp",
            "maxWspd",
            "opnStat",
            "totalIndex",
        ),
    ),
    (
        "sea_split_index",
        "SV_AP_01_003",
        "15142485",
        "바다갈라짐 체험지수",
        "fcstSeaSplitv2",
        "GetFcstSeaSplitApiServicev2",
        (),
        ("placeCode", "reqDate", "include", "exclude"),
        ("splocPstnNm", "lat", "lot", "predcYmd", "splocBgngDt", "splocEndDt", "totalIndex"),
    ),
    (
        "fishing_index",
        "SV_AP_01_004",
        "15142486",
        "바다낚시지수",
        "fcstFishingv2",
        "GetFcstFishingApiServicev2",
        ("gubun",),
        ("placeName", "reqDate", "include", "exclude"),
        ("seafsPstnNm", "lat", "lot", "predcYmd", "seafsTgfshNm", "totalIndex"),
    ),
    (
        "seasickness_index",
        "SV_AP_01_005",
        "15142487",
        "뱃멀미지수",
        "fcstSicknessv2",
        "GetFcstSicknessApiServicev2",
        (),
        ("nvgtCode", "reqDate", "include", "exclude"),
        ("nvgtNm", "vslNm", "lat", "lot", "predcYmd", "totalIndex"),
    ),
    (
        "skin_scuba_index",
        "SV_AP_01_006",
        "15142488",
        "스킨스쿠버지수",
        "fcstSkinScubav2",
        "GetFcstSkinScubaApiServicev2",
        (),
        ("placeCode", "reqDate", "include", "exclude"),
        ("skscExpcnRgnNm", "lat", "lot", "predcYmd", "totalIndex"),
    ),
    (
        "mudflat_index",
        "SV_AP_01_007",
        "15142489",
        "갯벌체험지수",
        "fcstMudflatv2",
        "GetFcstMudflatApiServicev2",
        (),
        ("placeCode", "reqDate", "include", "exclude"),
        ("mdftExpcnVlgNm", "lat", "lot", "predcYmd", "mdftExprnBgngTm", "mdftExprnEndTm"),
    ),
    (
        "surfing_index",
        "SV_AP_01_008",
        "15142490",
        "서핑지수",
        "fcstSurfingv2",
        "GetFcstSurfingApiServicev2",
        (),
        ("placeCode", "reqDate", "include", "exclude"),
        ("surfPlcNm", "lat", "lot", "predcYmd", "avgWvhgt", "avgWvpd", "totalIndex"),
    ),
    (
        "sea_trip_index",
        "SV_AP_01_009",
        "15142491",
        "바다여행지수",
        "fcstSeaTripv2",
        "GetFcstSeaTripApiServicev2",
        (),
        ("placeCode", "reqDate", "include", "exclude"),
        ("sareaDtlNm", "lat", "lot", "predcYmd", "weather", "totalIndex"),
    ),
    (
        "waterlogged",
        "SV_AP_01_010",
        "15142492",
        "연안 침수 정보",
        "waterlogged",
        "GetWaterloggedApiService",
        ("sggCd",),
        ("include", "exclude"),
        ("ctpvNm", "sggNm", "flodVlCn", "geom"),
    ),
    (
        "climate_sea_level",
        "SV_AP_01_011",
        "15142493",
        "지역 해양기후 수치모델 기반 미래 해수면 상승 전망",
        "changeClimateRising",
        "GetChangeClimateRisingApiService",
        ("ymin", "ymax", "xmin", "xmax"),
        ("include", "exclude"),
        ("sspSeCd", "swtrsfPredcSeCd", "lat", "lot", "svyVlCnt"),
    ),
    (
        "climate_salinity",
        "SV_AP_01_012",
        "15142494",
        "지역 해양기후 수치모델 기반 미래 표층염분 상승 전망",
        "changeClimateSlnt",
        "GetChangeClimateSlntApiService",
        ("ymin", "ymax", "xmin", "xmax"),
        ("include", "exclude"),
        ("sspSeCd", "swtrsfPredcSeCd", "lat", "lot", "svyVlCnt"),
    ),
    (
        "climate_water_temperature",
        "SV_AP_01_013",
        "15142495",
        "지역 해양기후 수치모델 기반 미래 표층수온 상승 전망",
        "changeClimateWtem",
        "GetChangeClimateWtemApiService",
        ("ymin", "ymax", "xmin", "xmax"),
        ("include", "exclude"),
        ("sspSeCd", "swtrsfPredcSeCd", "lat", "lot", "svyVlCnt"),
    ),
    (
        "climate_current",
        "SV_AP_01_014",
        "15142496",
        "지역 해양기후 수치모델 기반 미래 해수유동 변동 전망",
        "changeClimateFltg",
        "GetChangeClimateFltgApiService",
        ("ymin", "ymax", "xmin", "xmax"),
        ("include", "exclude"),
        ("sspSeCd", "swtrsfPredcSeCd", "lat", "lot", "svyVlCnt"),
    ),
    (
        "water_depth",
        "SV_AP_01_015",
        "15142498",
        "자연과학용 수심정보",
        "waterDepth",
        "GetWaterDepthApiService",
        ("ymin", "ymax", "xmin", "xmax"),
        ("include", "exclude"),
        ("lat", "lot", "dpwt"),
    ),
    (
        "seafog_appear",
        "SV_AP_02_001",
        "15142269",
        "해무 발생·소산정보",
        "seafogAppear",
        "GetSeafogAppearApiService",
        ("obsCode",),
        ("gubun", "reqDate", "startDate", "endDate", "include", "exclude"),
        ("obsvtrNm", "predcDt", "crctSfogRpblty", "sfogDspsRpblty"),
    ),
    (
        "seafog_cctv",
        "SV_AP_02_002",
        "15142499",
        "해무 CCTV 스틸컷",
        "seafogCctv",
        "GetSeafogCctvApiService",
        (),
        ("obsName", "reqDate", "include", "exclude"),
        ("sfogObsvtrNm", "imgCrtDt", "imgUrl"),
    ),
    (
        "seafog_range",
        "SV_AP_02_003",
        "15142501",
        "해무 판별정보",
        "seafogRange",
        "GetSeafogRangeApiService",
        ("obsCode",),
        ("reqDate", "include", "exclude"),
        ("obsvtrNm", "sfogJgmtDt", "sfogJgmtVlScr", "sfogJgmtVlCnt"),
    ),
    (
        "sailing_index",
        "SV_AP_02_004",
        "15142502",
        "항만해양지수",
        "sailing",
        "GetSailingApiService",
        ("obsName",),
        ("reqDate", "include", "exclude"),
        ("predcMdlId", "predcDt", "lat", "lot", "predcSeqStr", "predcSeq"),
    ),
    (
        "real_time_sea_current",
        "SV_AP_02_005",
        "15142503",
        "준실시간 해류도",
        "realTimeSeaCurrent",
        "GetRealTimeSeaCurrentApiService",
        ("sea",),
        ("reqDate", "include", "exclude"),
        ("ocSeNm", "obsrvnYmd", "urlAddr"),
    ),
    (
        "avg_sea_current",
        "SV_AP_02_006",
        "15142504",
        "평균 해류도",
        "avgSeaCurrent",
        "GetAvgSeaCurrentApiService",
        ("sea",),
        ("reqDate", "include", "exclude"),
        ("ocSeNm", "clsfDtlCdNm", "obsrvnDt", "urlAddr"),
    ),
    (
        "vortex",
        "SV_AP_02_007",
        "15142505",
        "소용돌이",
        "vortex",
        "GetVortexApiService",
        (),
        ("reqDate", "include", "exclude"),
        ("rcptnDt", "url"),
    ),
    (
        "survey_water_temp",
        "SV_AP_02_008",
        "15142506",
        "조위관측소 실측 수온",
        "surveyWaterTemp",
        "GetSurveyWaterTempApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lat", "lot", "obsrvnDt", "wtem"),
    ),
    (
        "survey_tide_level",
        "SV_AP_02_009",
        "15142507",
        "조위관측소 실측·예측 조위",
        "surveyTideLevel",
        "GetSurveyTideLevelApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lat", "lot", "obsrvnDt", "bscTdlvHgt", "tdlvHgt"),
    ),
    (
        "survey_air_temp",
        "SV_AP_02_010",
        "15142508",
        "조위관측소 실측 기온",
        "surveyAirTemp",
        "GetSurveyAirTempApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lat", "lot", "obsrvnDt", "artmp"),
    ),
    (
        "survey_air_press",
        "SV_AP_02_011",
        "15142509",
        "조위관측소 실측 기압",
        "surveyAirPress",
        "GetSurveyAirPressApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lat", "lot", "obsrvnDt", "atmpr"),
    ),
    (
        "survey_wind",
        "SV_AP_02_012",
        "15142518",
        "조위관측소 실측 풍향/풍속",
        "surveyWind",
        "GetSurveyWindApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lat", "lot", "obsrvnDt", "wndrct", "wspd"),
    ),
    (
        "survey_seafog",
        "SV_AP_02_013",
        "15142519",
        "해무관측소 최신 관측 데이터",
        "surveySeafog",
        "GetSurveySeafogApiService",
        ("obsCode",),
        ("reqDate", "include", "exclude"),
        ("obsvtrNm", "obsrvnDt", "lot", "lat", "rmyWspd", "rmyWndrct"),
    ),
    (
        "dt_recent",
        "SV_AP_03_001",
        "15155508",
        "조위관측소 최신 관측데이터",
        "dtRecent",
        "GetDTRecentApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnDt", "wndrct", "wspd", "wtem", "crdir", "crsp"),
    ),
    (
        "tw_recent",
        "SV_AP_03_002",
        "15155516",
        "해양관측부이 최신 관측데이터",
        "twRecent",
        "GetTWRecentApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnDt", "wvhgt", "wvpd", "wtem", "slnty"),
    ),
    (
        "hf_current",
        "SV_AP_03_003",
        "15155531",
        "해수유동 관측소 실측 유향·유속",
        "hfCurrent",
        "GetHFCurrentApiService",
        ("obsCode",),
        ("reqDate", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnDt", "crdir", "crsp"),
    ),
    (
        "noon_wave",
        "SV_AP_03_004",
        "15155994",
        "국가해양관측망 실측 파랑",
        "noonWave",
        "GetNoonWaveApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnDt", "wvhgt", "wvpd", "wvdrct"),
    ),
    (
        "ls_term_tide_obs",
        "SV_AP_03_005",
        "15156002",
        "장단기 조석관측",
        "lsTermTideObs",
        "GetLSTermTideObsApiService",
        ("obsCode",),
        ("include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnDt", "obsrvnVl"),
    ),
    (
        "noon_monthly_obs",
        "SV_AP_04_001",
        "15156005",
        "국가해양관측망 월간 관측자료(QC)",
        "noonMonthlyObs",
        "GetNoonMonthlyObsApiService",
        ("obsCode",),
        ("reqDate", "include", "exclude"),
        ("obsvtrTypeCd", "obsvtrNm", "lot", "lat", "obsrvnDt", "wtem", "slnty"),
    ),
    (
        "deviation_cal",
        "SV_AP_04_002",
        "15156011",
        "편차계산표(조석성과)",
        "deviationCal",
        "GetDeviationCalApiService",
        ("obsCode",),
        ("reqDate", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnDt", "obsTdlvVl", "predcDt", "predcTdlvVl"),
    ),
    (
        "extreme_tide_level",
        "SV_AP_04_003",
        "15156013",
        "최극조위(조석성과)",
        "extrmTideLvl",
        "GetExtrmTideLvlApiService",
        ("obsCode",),
        ("include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnYm", "hiwlv", "lowlv"),
    ),
    (
        "mean_sea_level",
        "SV_AP_04_004",
        "15156015",
        "평균해면성과표(조석성과)",
        "meanSeaLvl",
        "GetMeanSeaLvlApiService",
        ("obsCode",),
        ("include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnYm", "obsAvgTdlv"),
    ),
    (
        "hourly_tide",
        "SV_AP_04_005",
        "15156017",
        "1시간 조위(조석성과)",
        "hourlyTide",
        "GetHourlyTideApiService",
        ("obsCode",),
        ("reqDate", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnDt", "tdlvVl"),
    ),
    (
        "tide_forecast_high_low",
        "SV_AP_04_006",
        "15156018",
        "조석예보(고, 저조)",
        "tideFcstHghLw",
        "GetTideFcstHghLwApiService",
        ("obsCode",),
        ("reqDate", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "predcDt", "predcTdlvVl", "extrSe"),
    ),
    (
        "tide_forecast_time",
        "SV_AP_04_007",
        "15156022",
        "조석예보(시계열)",
        "tideFcstTime",
        "GetTideFcstTimeApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "predcDt", "tdlvHgt"),
    ),
    (
        "current_forecast_time",
        "SV_AP_04_008",
        "15156024",
        "조류예보(시계열)",
        "crntFcstTime",
        "GetCrntFcstTimeApiService",
        ("obsCode",),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "predcDt", "crdir", "crsp"),
    ),
    (
        "current_forecast_flood_ebb",
        "SV_AP_04_009",
        "15156025",
        "조류예보 최강창낙조 및 전류",
        "crntFcstFldEbb",
        "GetCrntFcstFldEbbApiService",
        ("obsCode",),
        ("include", "exclude"),
        ("obsvtrNm", "lot", "lat", "predcDt", "crdir", "crsp"),
    ),
    (
        "tidebed",
        "SV_AP_04_010",
        "15156026",
        "TideBED 예측 조위(1분)",
        "tidebed",
        "GetTidebedApiService",
        ("lot", "lat"),
        ("reqDate", "min", "include", "exclude"),
        ("obsvtrNm", "lot", "lat", "obsrvnDt", "obsrvnHgt", "jogo", "josi", "msl"),
    ),
    (
        "rip_current",
        "SV_AP_04_011",
        "15156028",
        "이안류 지수",
        "ripCurrent",
        "GetRipCurrentApiService",
        ("beachCode",),
        ("reqDate", "include", "exclude"),
        ("obsvtrId", "obsvtrNm", "lot", "lat", "obsrvnDt", "lastScr", "lastScrCn"),
    ),
    (
        "ship_index",
        "SV_AP_04_012",
        "15156036",
        "선박운항지수",
        "shipIndex",
        "GetShipIndexApiService",
        ("category",),
        ("vnpCode", "include", "exclude"),
        ("vslNvgtBrnchCdNm", "vslNm", "predcYmd", "predcTm", "lastScrCn"),
    ),
    (
        "ocean_condition",
        "SV_AP_04_013",
        "15156040",
        "해황예보도",
        "oceanCondition",
        "GetOceanConditionApiService",
        ("areaCode",),
        ("include", "exclude"),
        ("ofcBrnchId", "ofcBrnchNm", "ofcFrcstYmd", "ofcFrcstTm", "imgFileNm", "imgFilePath"),
    ),
)


def _build_service(row: tuple[object, ...]) -> ServiceDefinition:
    key, api_id, data_id, title, service_path, operation, required, optional, response = row
    if not isinstance(required, tuple):
        raise TypeError("required fields must be a tuple")
    if not isinstance(optional, tuple):
        raise TypeError("optional fields must be a tuple")
    if not isinstance(response, tuple):
        raise TypeError("response fields must be a tuple")
    aliases = (str(api_id), str(operation), str(operation).lower(), str(title))
    return ServiceDefinition(
        key=str(key),
        api_id=str(api_id),
        data_go_kr_id=str(data_id),
        title=str(title),
        category=_category(str(api_id)),
        service_path=str(service_path),
        operation=str(operation),
        required_params=tuple(str(item) for item in required),
        optional_params=tuple(str(item) for item in optional),
        response_fields=tuple(str(item) for item in response),
        aliases=aliases,
    )


SERVICE_DEFINITIONS: Final[tuple[ServiceDefinition, ...]] = tuple(
    _build_service(row) for row in _SERVICE_ROWS
)

SERVICE_BY_KEY: Final[dict[str, ServiceDefinition]] = {
    alias.lower(): service
    for service in SERVICE_DEFINITIONS
    for alias in (service.key, *service.aliases)
}


def get_service(key: str | ServiceDefinition) -> ServiceDefinition:
    """Return a service definition by key, API ID, operation name, or Korean title."""

    if isinstance(key, ServiceDefinition):
        return key
    try:
        return SERVICE_BY_KEY[key.lower()]
    except KeyError as exc:
        known = ", ".join(service.key for service in SERVICE_DEFINITIONS)
        raise KeyError(f"unknown KHOA ODMI service {key!r}; known keys: {known}") from exc
