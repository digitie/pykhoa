# 테스트

로컬 기본 검증은 실제 네트워크 호출 없이 실행합니다. HTTP 레이어는
`httpx.AsyncClient` 기반이며, 동기 public API는 같은 async 구현을 감싸는
facade로 검증합니다.

```bash
python -m compileall src/khoa tests
python -m pytest
python -m ruff check .
python -m mypy src/khoa
```

`tests/test_generated_fixtures.py`는 `tests/fixtures/**/*.json`을 자동으로 읽어
replay 기반 회귀 테스트를 수행합니다. 이 테스트는 저장된 `response.body`를
parser/processor에 다시 넣어 `processed` 결과를 비교하며, 외부 API를 호출하지
않습니다.

새 fixture function을 추가할 때는 `tests/runners.py`의 `RUNNERS`에 parse/process
함수를 등록합니다. fixture마다 별도 테스트 파일을 생성하지 않습니다. 지원되는
assertion mode는 `snapshot`, `schema_only`, `required_fields`, `count`입니다.

live test는 data.go.kr 실제 서비스를 호출하므로 명시적으로 켤 때만 실행합니다.

```bash
PYKHOA_RUN_LIVE=1 KHOA_SERVICE_KEY=... python -m pytest -m live
```

현재 live test가 확인하는 엔드포인트는 아래와 같습니다.

- `vortex/GetVortexApiService`
- `roms/GetRomsApiService`

KHOA ODMI 서비스는 data.go.kr를 통해 제공되며 서비스별 활용신청/승인이 필요할
수 있습니다. HTTP 403은 보통 인증키가 해당 서비스에서 거부된 상태입니다.
data.go.kr에서 대상 서비스 활용신청/승인을 받은 뒤 다시 실행합니다.
