"""
filters.py
Panel de filtros dinámicos y relacionados (en cascada) para las pestañas
analíticas. Se apoya en analytics.get_filter_options, que recalcula las
opciones disponibles de cada filtro considerando los demás ya seleccionados.
"""

import streamlit as st
import pandas as pd

from analytics import FILTER_COLUMNS, get_filter_options


def render_filters(df: pd.DataFrame, key_prefix: str) -> dict:
    st.sidebar.markdown("### 🔎 Filtros")

    if df.empty:
        st.sidebar.info("Aún no hay datos cargados en la base histórica.")
        return {"selections": {}, "date_range": None}

    if "fecha" in df.columns and df["fecha"].notna().any():
        min_d = pd.to_datetime(df["fecha"]).min()
        max_d = pd.to_datetime(df["fecha"]).max()
        date_range = st.sidebar.date_input(
            "Rango de fechas", value=(min_d.date(), max_d.date()),
            min_value=min_d.date(), max_value=max_d.date(),
            key=f"{key_prefix}_daterange",
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            date_range = (date_range[0], date_range[1])
        else:
            date_range = None
    else:
        date_range = None

    selections = {}
    if f"{key_prefix}_selections" not in st.session_state:
        st.session_state[f"{key_prefix}_selections"] = {}

    current = st.session_state[f"{key_prefix}_selections"]

    for label, col in FILTER_COLUMNS:
        if col not in df.columns:
            continue
        options = get_filter_options(df, col, current)
        if not options:
            continue
        default = current.get(col, [])
        default = [d for d in default if d in options]
        chosen = st.sidebar.multiselect(label, options, default=default, key=f"{key_prefix}_{col}")
        selections[col] = chosen

    st.session_state[f"{key_prefix}_selections"] = selections

    if st.sidebar.button("🧹 Limpiar filtros", key=f"{key_prefix}_clear"):
        st.session_state[f"{key_prefix}_selections"] = {}
        for label, col in FILTER_COLUMNS:
            st.session_state.pop(f"{key_prefix}_{col}", None)
        st.rerun()

    return {"selections": selections, "date_range": date_range}


def render_agrupacion_selector(key_prefix: str, opciones=None) -> str:
    opciones = opciones or ["Día", "Semana", "Mes", "Producto", "Lote", "Turno", "Línea", "Cliente"]
    return st.radio(
        "Visualizar por:", opciones, horizontal=True, key=f"{key_prefix}_agrupacion",
    )
