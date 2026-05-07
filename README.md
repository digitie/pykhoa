# pykhoa

Unofficial Python client for KHOA Badanuri ODMI OpenAPI services published through
data.go.kr.

The bundled catalog follows KHOA's ODMI OpenAPI list:

<https://www.khoa.go.kr/oceandata/openapi/odmi/odmiApiList.do>

## Install

```bash
pip install -e .
```

## Quick Start

```python
from pykhoa import KhoaClient

client = KhoaClient.from_env()  # KHOA_SERVICE_KEY

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

`fetch()` accepts a service key from `pykhoa.SERVICE_DEFINITIONS` by key, KHOA
`api_id`, operation name, or Korean title.

Snake-case aliases are accepted for common KHOA parameters:

```python
page = client.fetch("dt_recent", obs_code="DT_0001", req_date="20260507")
```

For ROMS rows, a typed helper is included:

```python
page = client.roms(ymin=34.0, ymax=34.1, xmin=123.2, xmax=123.3)
prediction = page.items[0]
print(prediction.predicted_at, prediction.water_temperature_c)
```

Every service key is also available as a dynamic convenience method:

```python
page = client.rip_current(beach_code="BCH001", req_date="20260507")
```

## Catalog

```python
from pykhoa import SERVICE_DEFINITIONS

for service in SERVICE_DEFINITIONS:
    print(service.key, service.title, service.required_params, service.requested_url)
```

The catalog currently contains the 46 국가중점 ODMI service detail pages exposed by
KHOA, including ROMS, marine leisure indexes, sea-fog services, tide/current
observations and forecasts, TideBED, rip-current, ship-index, and ocean-condition
map services.

## Tests

```bash
python -m pytest
python -m ruff check .
python -m mypy pykhoa
```

Live tests call real data.go.kr KHOA ODMI services and require an approved key:

```bash
PYKHOA_RUN_LIVE=1 KHOA_SERVICE_KEY=... python -m pytest -m live
```

If data.go.kr returns HTTP 403, the key is valid enough to reach the gateway but
is not authorized for the requested KHOA ODMI service. Apply for the target
service on data.go.kr, then rerun the live tests.
