"""Streamlit 기반 KHOA API 디버그 카탈로그 뷰어."""
# ruff: noqa: E402,I001

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
for module_name, module in list(sys.modules.items()):
    if module_name != "khoa" and not module_name.startswith("khoa."):
        continue
    module_file = getattr(module, "__file__", None)
    if module_file is not None and not Path(module_file).resolve().is_relative_to(SRC):
        del sys.modules[module_name]

try:
    import pandas as pd
    import streamlit as st
except ModuleNotFoundError as exc:  # pragma: no cover - 선택 실행 도구
    raise SystemExit('Streamlit UI를 쓰려면 `pip install -e ".[debug-ui]"`를 실행하세요.') from exc

from khoa import (
    KhoaClient,
    get_api_catalog,
    get_service_key,
    jsonable,
    load_env_file,
    save_fixture,
)


@dataclass(frozen=True)
class ParameterSpec:
    """디버그 UI에서 요청 파라미터 입력 폼을 만들기 위한 최소 명세."""

    name: str
    required: bool
    label: str
    placeholder: str = ""
    help: str = ""
    default: str = ""


def _param(
    name: str,
    *,
    required: bool,
    label: str | None = None,
    placeholder: str = "",
    help: str = "",
    default: str = "",
) -> ParameterSpec:
    return ParameterSpec(
        name=name,
        required=required,
        label=label or name,
        placeholder=placeholder,
        help=help,
        default=default,
    )


def main() -> None:
    st.set_page_config(page_title="KHOA API Debug", layout="wide")
    st.title("KHOA API Debug")

    rows = list(get_api_catalog())
    sources = sorted({row["data_source"] for row in rows})
    source = st.sidebar.selectbox("Data source", sources)
    source_rows = [row for row in rows if row["data_source"] == source]
    labels = [row["dataset_label"] for row in source_rows]
    selected_label = st.sidebar.selectbox("API", labels)
    selected = source_rows[labels.index(selected_label)]

    st.sidebar.caption("API full name")
    st.sidebar.write(_api_full_name(selected))
    st.sidebar.caption(_api_description(selected))

    env_names = tuple(str(name) for name in selected["service_key_env_names"])
    default_key = get_service_key(source) or ""
    env_sources = _env_key_sources(env_names)

    environment = "manual"
    if env_sources:
        st.sidebar.subheader("Environment")
        environment = st.sidebar.selectbox("Environment", ["env", "manual"])
        if environment == "env":
            source_info = env_sources[0]
            st.sidebar.caption(
                f"{source_info['name']} 값을 사용합니다. Source: {source_info['source']}"
            )

    st.sidebar.subheader("Auth")
    if environment == "manual":
        api_key = st.sidebar.text_input(
            "serviceKey",
            value="",
            type="password",
            placeholder="직접 입력",
            help=f"사용 가능한 env 이름: {', '.join(env_names)}",
        )
        effective_api_key = api_key
    else:
        effective_api_key = default_key
    _service_key_links(selected)

    timeout = st.sidebar.number_input(
        "Timeout",
        min_value=1.0,
        max_value=60.0,
        value=10.0,
        step=1.0,
        help="API 요청 timeout seconds입니다.",
    )
    fixture_base_dir = _fixture_base_dir_sidebar()

    tabs = st.tabs(
        [
            "Raw Response",
            "Pydantic Model",
            "Processed Result",
            "Validation Errors",
            "Debug Trace",
            "Fixture / Testcase",
        ]
    )

    with tabs[0]:
        _raw_response_tab(selected, effective_api_key, timeout=float(timeout))
    with tabs[1]:
        _pydantic_model_tab(selected)
    with tabs[2]:
        _processed_result_tab(selected)
    with tabs[3]:
        _validation_errors_tab(selected)
    with tabs[4]:
        _debug_trace_tab(rows, selected, env_names)
    with tabs[5]:
        _fixture_tab(fixture_base_dir, selected)


def _raw_response_tab(selected: dict[str, Any], api_key: str, *, timeout: float) -> None:
    st.subheader(selected["dataset_name"])
    st.caption(f"{selected['data_source']} / {selected['service_path']} / {selected['operation']}")

    try:
        submitted, params, request_options, missing = _request_form(selected)
    except ValueError as exc:
        st.error(str(exc))
        return

    preview = {
        **params,
        "pageNo": request_options["page_no"],
        "numOfRows": request_options["num_of_rows"],
        "type": request_options["response_type"],
    }
    st.subheader("Request params preview")
    st.json(preview)

    if not submitted:
        return
    if missing:
        st.error("필수 파라미터를 입력하세요: " + ", ".join(missing))
        return

    try:
        client = KhoaClient(
            api_key=api_key or None,
            key_source=selected["data_source"],
            timeout=timeout,
            retries=0,
        )
        run = client.debug_fetch(
            selected["service_key"],
            params=params,
            page_no=request_options["page_no"],
            num_of_rows=request_options["num_of_rows"],
            response_type=request_options["response_type"],
        )
    except Exception as exc:  # pragma: no cover - UI 표시
        st.error(str(exc))
        return

    _store_run(selected, run)
    if run.error:
        st.error(run.error["message"])
    st.json(jsonable(run.response))


def _request_form(
    selected: dict[str, Any],
) -> tuple[bool, dict[str, Any], dict[str, Any], list[str]]:
    specs = _parameter_specs(selected)
    required_specs = [spec for spec in specs if spec.required]
    optional_specs = [spec for spec in specs if not spec.required]
    key_prefix = f"{selected['data_source']}:{selected['service_key']}"

    with st.form(f"request-form:{key_prefix}"):
        st.subheader("Required parameters")
        if required_specs:
            required_values = _render_param_grid(required_specs, key_prefix=key_prefix)
        else:
            st.caption("이 API에는 필수 파라미터가 없습니다.")
            required_values = {}

        st.subheader("Optional parameters")
        optional_values = _render_param_grid(optional_specs, key_prefix=key_prefix)
        page_no, num_of_rows, response_type = _render_common_options(key_prefix)

        extra_text = st.text_area(
            "Extra params JSON",
            value="{}",
            height=110,
            help="폼에 없는 provider 파라미터를 JSON object로 추가합니다.",
            key=f"{key_prefix}:extra",
        )
        submitted = st.form_submit_button("Run selected API")

    params = {**required_values, **optional_values, **_parse_extra_params(extra_text)}
    missing = [spec.name for spec in required_specs if not str(params.get(spec.name, "")).strip()]
    return (
        submitted,
        {key: value for key, value in params.items() if str(value).strip()},
        {"page_no": page_no, "num_of_rows": num_of_rows, "response_type": response_type},
        missing,
    )


def _parameter_specs(selected: dict[str, Any]) -> tuple[ParameterSpec, ...]:
    required = tuple(str(name) for name in selected["required_params"])
    optional = tuple(
        str(name)
        for name in selected["optional_params"]
        if name not in {"include", "exclude"}
    )
    return tuple(
        _param(
            name,
            required=True,
            label=name,
            help="KHOA ODMI 필수 요청 파라미터입니다.",
        )
        for name in required
    ) + tuple(
        _param(
            name,
            required=False,
            label=name,
            help="KHOA ODMI 선택 요청 파라미터입니다.",
        )
        for name in optional
    )


def _render_param_grid(specs: tuple[ParameterSpec, ...], *, key_prefix: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for index in range(0, len(specs), 2):
        columns = st.columns(2)
        for column, spec in zip(columns, specs[index : index + 2], strict=False):
            with column:
                values[spec.name] = st.text_input(
                    spec.label,
                    value=spec.default,
                    placeholder=spec.placeholder,
                    help=spec.help or None,
                    key=f"{key_prefix}:param:{spec.name}",
                )
    return values


def _render_common_options(key_prefix: str) -> tuple[int, int, str]:
    col1, col2, col3 = st.columns(3)
    with col1:
        page_no = st.number_input(
            "pageNo",
            min_value=1,
            value=1,
            step=1,
            help="공공데이터포털 paging 파라미터입니다.",
            key=f"{key_prefix}:pageNo",
        )
    with col2:
        num_of_rows = st.number_input(
            "numOfRows",
            min_value=1,
            value=10,
            step=1,
            help="한 페이지에 받을 row 수입니다.",
            key=f"{key_prefix}:numOfRows",
        )
    with col3:
        response_type = st.selectbox(
            "type",
            ["json", "xml"],
            index=0,
            help="KHOA ODMI response type입니다.",
            key=f"{key_prefix}:type",
        )
    return int(page_no), int(num_of_rows), str(response_type)


def _parse_extra_params(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Extra params JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Extra params JSON must be an object")
    return {
        key: value
        for key, value in payload.items()
        if key not in {"serviceKey", "ServiceKey", "pageNo", "numOfRows", "type"}
    }


def _pydantic_model_tab(selected: dict[str, Any]) -> None:
    run = _current_run(selected)
    if run is None:
        st.info("Raw Response 탭에서 선택한 API를 실행하면 여기에서 Pydantic 모델을 확인합니다.")
        return
    if run.error:
        st.warning("실행 중 오류가 있습니다. Validation Errors 탭을 확인하세요.")
    st.json(jsonable(run.parsed))


def _processed_result_tab(selected: dict[str, Any]) -> None:
    run = _current_run(selected)
    if run is None:
        st.info("Raw Response 탭에서 API를 실행하면 처리된 row preview를 표시합니다.")
        return
    data = jsonable(run.processed)
    if isinstance(data, list) and data:
        st.dataframe(pd.json_normalize(data, sep="."), width="stretch", hide_index=True)
    else:
        st.json(data)


def _validation_errors_tab(selected: dict[str, Any]) -> None:
    run = _current_run(selected)
    if run is None:
        st.info("아직 실행된 API가 없습니다.")
        return
    if not run.error:
        st.success("현재 실행 결과에서 validation error 또는 exception이 없습니다.")
        return
    st.error(run.error["message"])
    st.json(run.error)


def _debug_trace_tab(
    rows: list[dict[str, Any]],
    selected: dict[str, Any],
    env_names: tuple[str, ...],
) -> None:
    run = _current_run(selected)

    st.subheader("Catalog")
    st.dataframe(rows, width="stretch", hide_index=True)

    st.subheader("Selected API")
    st.json(selected)
    st.link_button("serviceKey 발급/확인", selected["service_key_url"])
    st.caption(f"credential env: {', '.join(env_names)}")

    if run is not None:
        st.subheader("Trace")
        st.write(run.trace)
        if run.catalog is not None:
            st.dataframe(
                pd.json_normalize([run.catalog], sep="."),
                width="stretch",
                hide_index=True,
            )


def _fixture_tab(fixture_base_dir: str, selected: dict[str, Any]) -> None:
    run = _current_run(selected)
    if run is None:
        st.info("Raw Response 탭에서 API를 실행한 뒤 fixture를 저장할 수 있습니다.")
        st.caption("Fixture base dir")
        st.code(fixture_base_dir, language=None)
        return

    with st.expander("Save as fixture", expanded=True):
        case_name = st.text_input("Case name", value=f"{selected['service_key']}_normal")
        description = st.text_area("Description", value=f"{selected['dataset_name']} 정상 케이스")
        assertion_mode = st.selectbox(
            "Assertion mode",
            ["snapshot", "schema_only", "required_fields", "count"],
        )
        exclude_fields_raw = st.text_input(
            "Exclude fields",
            value="fetched_at, request_id, updated_at",
        )
        required_fields_raw = st.text_input("Required fields", value="")
        overwrite = st.checkbox("Overwrite existing fixture", value=False)

        assertion = {
            "mode": assertion_mode,
            "exclude_fields": [
                value.strip() for value in exclude_fields_raw.split(",") if value.strip()
            ],
            "required_fields": [
                value.strip() for value in required_fields_raw.split(",") if value.strip()
            ],
        }

        st.subheader("Fixture preview")
        st.json(
            {
                "function": selected["service_key"],
                "input": jsonable(run.input),
                "request": jsonable(run.request),
                "response": jsonable(run.response),
                "processed": jsonable(run.processed),
                "assertion": assertion,
            }
        )

        if st.button("Save as fixture"):
            try:
                path = save_fixture(
                    base_dir=fixture_base_dir,
                    function_name=selected["service_key"],
                    case_name=case_name,
                    description=description,
                    input_data=run.input,
                    request_data=run.request,
                    response_data=run.response,
                    parsed_result=run.parsed,
                    processed_result=run.processed,
                    assertion=assertion,
                    overwrite=overwrite,
                )
            except Exception as exc:  # pragma: no cover - UI 표시
                st.error(str(exc))
            else:
                st.success(f"Saved: {path}")


def _service_key_links(selected: dict[str, Any]) -> None:
    st.sidebar.caption("Service key links")
    st.sidebar.link_button("serviceKey 발급/확인", selected["service_key_url"])
    if selected["khoa_detail_url"] != selected["service_key_url"]:
        st.sidebar.link_button("KHOA 카탈로그", selected["khoa_detail_url"])


def _env_key_sources(env_names: tuple[str, ...]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    for name in env_names:
        value = os.getenv(name)
        if value is not None and value.strip():
            sources.append({"name": name, "source": "process env"})
            return sources

    local_env = load_env_file(ROOT / ".env")
    for name in env_names:
        value = local_env.get(name)
        if value is not None and value.strip():
            sources.append({"name": name, "source": ".env"})
            return sources
    return sources


def _fixture_base_dir_sidebar() -> str:
    st.sidebar.subheader("Fixtures")
    candidates = _fixture_dir_candidates()
    options = [str(path) for path in candidates]
    custom_label = "Custom..."
    selected = st.sidebar.selectbox("Fixture base dir", [*options, custom_label])
    if selected == custom_label:
        selected = st.sidebar.text_input(
            "Custom fixture base dir",
            value=str((ROOT / "tests" / "fixtures").resolve()),
        )
    st.sidebar.caption(selected)
    return selected


def _fixture_dir_candidates() -> list[Path]:
    preferred = [
        ROOT / "tests" / "fixtures",
        ROOT / "tests",
        ROOT / "examples",
        ROOT,
    ]
    candidates: list[Path] = []
    for path in preferred:
        resolved = path.resolve()
        if resolved not in candidates:
            candidates.append(resolved)
    return candidates


def _store_run(selected: dict[str, Any], run: Any) -> None:
    st.session_state["last_run"] = {
        "selection_key": _selection_key(selected),
        "run": run,
    }


def _current_run(selected: dict[str, Any]) -> Any | None:
    stored = st.session_state.get("last_run")
    if not isinstance(stored, dict):
        return None
    if stored.get("selection_key") != _selection_key(selected):
        return None
    return stored.get("run")


def _selection_key(selected: dict[str, Any]) -> str:
    return f"{selected['data_source']}:{selected['service_key']}"


def _api_full_name(selected: dict[str, Any]) -> str:
    return f"{selected['dataset_name']} / {selected['service_path']} / {selected['operation']}"


def _api_description(selected: dict[str, Any]) -> str:
    required = ", ".join(selected["required_params"]) or "필수 파라미터 없음"
    return f"{selected['dataset_name']} API입니다. Required: {required}"


if __name__ == "__main__":
    main()
