from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from extractor import (
    ExtractionError,
    extract_entities_and_layers,
    get_odafc_status,
    read_saved_converter_path,
)


st.set_page_config(page_title="DWG Entity Extractor", page_icon="📐", layout="wide")
st.title("DWG/DXF Entity and Layer Extractor")
st.caption("Upload a DWG file to list entities and layers. If direct DWG read fails, the app attempts DWG->DXF conversion and retries extraction.")

with st.sidebar:
    st.subheader("Setup")
    st.caption("Optional: point the app at a DWG converter binary or app bundle.")
    default_converter = st.session_state.get("converter_bin") or read_saved_converter_path() or ""
    converter_bin = st.text_input(
        "Converter path",
        value=default_converter,
        placeholder="/Applications/ODAFileConverter.app or /usr/local/bin/dwg2dxf",
        help="Path to ODAFileConverter, TeighaFileConverter, or dwg2dxf. If empty, the app auto-detects common locations and PATH.",
    )
    if converter_bin:
        st.session_state["converter_bin"] = converter_bin
    converter_path = Path(converter_bin).expanduser() if converter_bin else None
    odafc_ready, odafc_message = get_odafc_status(converter_path)
    if odafc_ready:
        st.success(f"ODA bridge ready: {odafc_message}")
    else:
        st.warning(f"ODA bridge not ready: {odafc_message}")
    show_debug_notes = st.checkbox("Show debug stage timings", value=True)
    timeout_sec = st.slider("DWG extraction timeout (seconds)", min_value=10, max_value=180, value=30, step=5)

uploaded = st.file_uploader("Upload DWG or DXF", type=["dwg", "dxf"])

if uploaded is not None:
    suffix = Path(uploaded.name).suffix.lower()
    with tempfile.TemporaryDirectory() as td:
        input_path = Path(td) / uploaded.name
        input_path.write_bytes(uploaded.getbuffer())

        try:
            result = extract_entities_and_layers(
                input_path=input_path,
                converter_bin=converter_path,
                timeout_sec=timeout_sec,
            )
        except ExtractionError as exc:
            st.error(str(exc))
            st.stop()

        if result.source_kind == "dwg":
            st.success("Read directly from DWG")
        else:
            st.warning("Direct DWG read failed. Used DXF fallback.")

        if result.notes:
            with st.expander("Processing notes", expanded=show_debug_notes):
                for note in result.notes:
                    st.write(f"- {note}")

        entities_df = pd.DataFrame(result.entities)
        layers_df = pd.DataFrame(result.layers)
        types_df = pd.DataFrame(result.entity_types)
        feature_counts = result.feature_counts or {"walls": 0, "windows": 0, "doors": 0}
        features_df = pd.DataFrame(result.feature_entities)

        measurement_cols = [
            "measurement_length",
            "measurement_area",
            "measurement_radius",
            "measurement_perimeter",
        ]
        present_measurement_cols = [col for col in measurement_cols if col in entities_df.columns]
        if present_measurement_cols:
            non_empty_measurements = entities_df[present_measurement_cols].fillna("").astype(str).apply(
                lambda col: col.str.strip() != ""
            )
            measurable_entities_df = entities_df[non_empty_measurements.any(axis=1)].copy()
        else:
            measurable_entities_df = entities_df.iloc[0:0].copy()

        c1, c2, c3 = st.columns(3)
        c1.metric("Entity rows", len(entities_df.index))
        c2.metric("Layers", max(0, len(layers_df.index) - 1) if "layer" in layers_df.columns else len(layers_df.index))
        total = None
        if not types_df.empty and "entity_type" in types_df.columns and "count" in types_df.columns:
            hit = types_df[types_df["entity_type"] == "TOTAL"]
            if not hit.empty:
                total = hit.iloc[0]["count"]
        c3.metric("Total entities", total if total is not None else len(entities_df.index))

        f1, f2, f3 = st.columns(3)
        f1.metric("Walls", int(feature_counts.get("walls", 0)))
        f2.metric("Windows", int(feature_counts.get("windows", 0)))
        f3.metric("Doors", int(feature_counts.get("doors", 0)))

        tabs = st.tabs(["Entities", "Measurements", "Features", "Layers", "Entity Types"])

        with tabs[0]:
            st.dataframe(entities_df, width="stretch", hide_index=True)
            st.download_button(
                "Download entities CSV",
                entities_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{Path(uploaded.name).stem}_entities.csv",
                mime="text/csv",
                width="stretch",
            )

        with tabs[1]:
            st.caption("Entities with at least one computed measurement value.")
            st.dataframe(measurable_entities_df, width="stretch", hide_index=True)
            st.download_button(
                "Download measurements CSV",
                measurable_entities_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{Path(uploaded.name).stem}_measurements.csv",
                mime="text/csv",
                width="stretch",
            )

        with tabs[2]:
            st.caption("Entities classified as walls, windows, or doors.")
            st.dataframe(features_df, width="stretch", hide_index=True)
            st.download_button(
                "Download features CSV",
                features_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{Path(uploaded.name).stem}_features.csv",
                mime="text/csv",
                width="stretch",
            )

        with tabs[3]:
            st.dataframe(layers_df, width="stretch", hide_index=True)
            st.download_button(
                "Download layers CSV",
                layers_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{Path(uploaded.name).stem}_layers.csv",
                mime="text/csv",
                width="stretch",
            )

        with tabs[4]:
            st.dataframe(types_df, width="stretch", hide_index=True)
            st.download_button(
                "Download entity types CSV",
                types_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{Path(uploaded.name).stem}_entity_types.csv",
                mime="text/csv",
                width="stretch",
            )

else:
    st.info("Upload a DWG/DXF file to start extraction.")
