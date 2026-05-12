# 테스트

로컬 기본 검증은 실제 네트워크 호출 없이 실행합니다.

```bash
python -m compileall src/khoa tests
python -m pytest
python -m ruff check .
python -m mypy src/khoa
```

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
