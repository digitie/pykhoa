"""python-khoa-api용 최소 Streamlit 디버그 UI 예제.

실행 예:

    streamlit run examples/streamlit_debug_ui.py

이 파일은 예제이며, `khoa` 패키지는 Streamlit에 직접 의존하지 않습니다.
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from khoa import KhoaClient, get_api_catalog, jsonable


def _default_params(entry: dict[str, Any]) -> dict[str, Any]:
    return {name: "" for name in entry["required_params"]}


def _parse_params(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Input parameters must be a JSON object")
    return parsed


catalog = list(get_api_catalog())
entry_by_label = {entry["dataset_label"]: entry for entry in catalog}

st.set_page_config(page_title="KHOA API Debug", layout="wide")
st.title("KHOA API Debug")

with st.sidebar:
    selected_label = st.selectbox("Dataset", list(entry_by_label))
    selected_entry = entry_by_label[selected_label]
    api_key = st.text_input("Service key", type="password")
    timeout = st.number_input("Timeout", min_value=1.0, max_value=60.0, value=10.0, step=1.0)
    st.link_button("서비스키 받기", selected_entry["service_key_url"])

st.caption(selected_entry["endpoint"])
params_raw = st.text_area(
    "Input parameters",
    value=json.dumps(_default_params(selected_entry), ensure_ascii=False, indent=2),
    height=180,
)

run = None
if st.button("Run", type="primary"):
    try:
        params = _parse_params(params_raw)
        client = KhoaClient(
            api_key=api_key or None,
            key_source=selected_entry["data_source"],
            timeout=timeout,
            retries=0,
        )
        run = client.debug_fetch(selected_entry["service_key"], **params)
        st.session_state["debug_run"] = run
    except Exception as exc:
        st.error(f"{exc.__class__.__name__}: {exc}")

run = st.session_state.get("debug_run")

raw_tab, parsed_tab, processed_tab, error_tab, trace_tab, fixture_tab = st.tabs(
    [
        "Raw Response",
        "Pydantic Model",
        "Processed Result",
        "Validation Errors",
        "Debug Trace",
        "Fixture",
    ]
)

if run is not None:
    with raw_tab:
        st.json(jsonable(run.response))

    with parsed_tab:
        st.json(jsonable(run.parsed))

    with processed_tab:
        st.json(jsonable(run.processed))

    with error_tab:
        st.json(jsonable(run.error))

    with trace_tab:
        st.write(run.trace)
        if run.catalog is not None:
            st.dataframe(pd.json_normalize([run.catalog], sep="."))
            st.link_button("선택 API 서비스키 받기", run.catalog["service_key_url"])

    with fixture_tab:
        st.json(
            {
                "function": run.input.get("service"),
                "input": jsonable(run.input),
                "request": jsonable(run.request),
                "response": jsonable(run.response),
                "processed": jsonable(run.processed),
            }
        )
