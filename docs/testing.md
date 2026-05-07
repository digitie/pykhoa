# Testing

Run local checks:

```bash
python -m pytest
python -m ruff check .
python -m mypy pykhoa
```

Live tests are opt-in to avoid accidental calls to data.go.kr:

```bash
PYKHOA_RUN_LIVE=1 KHOA_SERVICE_KEY=... python -m pytest -m live
```

The live tests currently smoke-test:

- `vortex/GetVortexApiService`
- `roms/GetRomsApiService`

KHOA ODMI services are published through data.go.kr and may require service-level
approval. HTTP 403 means the key was rejected for that service; apply for the
service on data.go.kr and retry.
