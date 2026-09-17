"""
analytics.py
Cálculos analíticos sobre el DataFrame histórico ya cargado desde la base.

Distinción explícita de porcentajes (requisito 15 del pliego):
- % INCIDENCIA = unidades afectadas / unidades inspeccionadas * 100
    -> usa como base la cantidad de UNIDADES INSPECCIONADAS
- % COMPOSICIÓN = casos de una causal / total de casos (defectos) * 100
    -> usa como base el TOTAL DE DEFECTOS, no las unidades inspeccionadas
    (una misma unidad puede tener más de un defecto)
"""

import pandas as pd
import numpy as np

from config import (
    TIPO_INSPECCION, TIPO_DEFECTO, TIPO_DEGRADACION, TIPO_PERDIDA_VACIO,
    DEGRADACION_PROPIA, DEGRADACION_NO_PROPIA,
)

GROUP_LABELS = {
    "Día": "fecha",
    "Semana": "semana",
    "Mes": "mes",
    "Producto": "producto",
    "Lote": "lote",
    "Turno": "turno",
    "Línea": "linea",
    "Cliente": "cliente",
}


# ---------------------------------------------------------------------------
# FILTROS
# ---------------------------------------------------------------------------
FILTER_COLUMNS = [
    ("Año", "anio"), ("Mes", "mes"), ("Semana", "semana"),
    ("Producto", "producto"), ("Especie", "especie"), ("Cliente", "cliente"),
    ("Lote", "lote"), ("Turno", "turno"), ("Línea", "linea"),
    ("Máquina", "maquina"), ("Centro/Origen", "centro"),
    ("Inspector", "inspector"), ("Categoría defecto", "categoria_defecto"),
]


def get_filter_options(df: pd.DataFrame, col: str, current_filters: dict = None):
    """Devuelve valores únicos disponibles para 'col', aplicando los demás
    filtros ya seleccionados (filtros relacionados/cascada)."""
    if df.empty or col not in df.columns:
        return []
    sub = df.copy()
    current_filters = current_filters or {}
    for k, v in current_filters.items():
        if k == col or not v:
            continue
        if k in sub.columns:
            sub = sub[sub[k].isin(v)]
    values = sub[col].dropna().unique().tolist()
    try:
        values = sorted(values)
    except TypeError:
        values = sorted(values, key=str)
    return values


def apply_filters(df: pd.DataFrame, filters: dict, date_range=None) -> pd.DataFrame:
    out = df.copy()
    for col, values in (filters or {}).items():
        if values and col in out.columns:
            out = out[out[col].isin(values)]
    if date_range and "fecha" in out.columns:
        start, end = date_range
        if start is not None:
            out = out[(out["fecha"].isna()) | (out["fecha"] >= pd.Timestamp(start))]
        if end is not None:
            out = out[(out["fecha"].isna()) | (out["fecha"] <= pd.Timestamp(end))]
    return out


# ---------------------------------------------------------------------------
# KPIs RESUMEN EJECUTIVO
# ---------------------------------------------------------------------------
def calc_kpis(df: pd.DataFrame) -> dict:
    insp = df[df["tipo_registro"] == TIPO_INSPECCION]
    defectos = df[df["tipo_registro"] == TIPO_DEFECTO]
    degrad = df[df["tipo_registro"] == TIPO_DEGRADACION]
    vacio = df[df["tipo_registro"] == TIPO_PERDIDA_VACIO]

    total_inspeccionadas = insp["unidades_inspeccionadas"].sum()
    if total_inspeccionadas == 0 or pd.isna(total_inspeccionadas):
        # si no hay registros de tipo inspección, usar la suma disponible en
        # cualquier registro que traiga ese campo informado
        total_inspeccionadas = df["unidades_inspeccionadas"].dropna().sum()

    total_defectos_cant = defectos["cantidad"].sum()
    total_degrad_cant = degrad["cantidad"].sum()
    total_vacio_cant = vacio["cantidad"].sum()

    def pct(numer, denom):
        if not denom or pd.isna(denom) or denom == 0:
            return None
        return round(100 * numer / denom, 2)

    aceptabilidad = None
    if total_inspeccionadas:
        rechazadas = insp["unidades_rechazadas"].sum()
        aceptadas = insp["unidades_aceptadas"].sum()
        if aceptadas and not pd.isna(aceptadas):
            aceptabilidad = pct(aceptadas, total_inspeccionadas)
        elif not pd.isna(rechazadas):
            aceptabilidad = round(100 - pct(rechazadas, total_inspeccionadas), 2) if pct(rechazadas, total_inspeccionadas) is not None else None

    kpis = {
        "total_inspeccionadas": total_inspeccionadas,
        "pct_aceptabilidad": aceptabilidad,
        "pct_defectuosidad": pct(total_defectos_cant, total_inspeccionadas),
        "pct_degradacion": pct(total_degrad_cant, total_inspeccionadas),
        "pct_perdida_vacio": pct(total_vacio_cant, total_inspeccionadas),
        "total_defectos": total_defectos_cant,
        "principal_causal_defecto": _top_causal(defectos),
        "principal_causal_degradacion": _top_causal(degrad),
        "principal_causal_vacio": _top_causal(vacio),
    }
    return kpis


def _top_causal(df_subset: pd.DataFrame):
    if df_subset.empty or "causal" not in df_subset.columns:
        return None
    agg = df_subset.groupby("causal")["cantidad"].sum().sort_values(ascending=False)
    if agg.empty:
        return None
    return f"{agg.index[0]} ({int(agg.iloc[0])} casos)"


# ---------------------------------------------------------------------------
# INCIDENCIA vs COMPOSICIÓN
# ---------------------------------------------------------------------------
def calc_incidencia_por_grupo(df_eventos: pd.DataFrame, df_base_inspeccion: pd.DataFrame,
                               group_col: str) -> pd.DataFrame:
    """% incidencia = casos del grupo / unidades inspeccionadas del grupo * 100"""
    if group_col not in df_eventos.columns:
        return pd.DataFrame(columns=[group_col, "cantidad", "unidades_inspeccionadas", "pct_incidencia"])

    casos = df_eventos.groupby(group_col, dropna=True)["cantidad"].sum().reset_index()
    base = df_base_inspeccion.groupby(group_col, dropna=True)["unidades_inspeccionadas"].sum().reset_index()
    out = casos.merge(base, on=group_col, how="left")
    out["pct_incidencia"] = np.where(
        (out["unidades_inspeccionadas"].fillna(0) > 0),
        100 * out["cantidad"] / out["unidades_inspeccionadas"],
        np.nan,
    ).round(2)
    return out.sort_values("cantidad", ascending=False)


def calc_composicion(df_eventos: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """% composición = casos de la categoría / total de casos * 100"""
    if group_col not in df_eventos.columns or df_eventos.empty:
        return pd.DataFrame(columns=[group_col, "cantidad", "pct_composicion"])
    agg = df_eventos.groupby(group_col, dropna=True)["cantidad"].sum().reset_index()
    total = agg["cantidad"].sum()
    agg["pct_composicion"] = (100 * agg["cantidad"] / total).round(2) if total else 0
    return agg.sort_values("cantidad", ascending=False)


# ---------------------------------------------------------------------------
# DEGRADACIONES
# ---------------------------------------------------------------------------
def calc_degradaciones(df: pd.DataFrame) -> dict:
    degrad = df[df["tipo_registro"] == TIPO_DEGRADACION].copy()
    degrad["clase"] = np.where(
        degrad["causal"].isin(DEGRADACION_PROPIA), "Propia",
        np.where(degrad["causal"].isin(DEGRADACION_NO_PROPIA), "No Propia", "Sin Clasificar"),
    )
    resumen_clase = degrad.groupby("clase")["cantidad"].sum().reset_index()
    por_causal = calc_composicion(degrad, "causal")
    return {
        "detalle": degrad,
        "por_clase": resumen_clase,
        "por_causal": por_causal,
    }


# ---------------------------------------------------------------------------
# PÉRDIDA DE VACÍO
# ---------------------------------------------------------------------------
def calc_perdida_vacio(df: pd.DataFrame) -> dict:
    vacio = df[df["tipo_registro"] == TIPO_PERDIDA_VACIO].copy()
    por_sector = calc_composicion(vacio, "sector")
    por_causal = calc_composicion(vacio, "causal")

    matriz = pd.DataFrame()
    if not vacio.empty and "sector" in vacio.columns and "causal" in vacio.columns:
        matriz = vacio.pivot_table(
            index="sector", columns="causal", values="cantidad",
            aggfunc="sum", fill_value=0,
        )
    return {
        "detalle": vacio,
        "por_sector": por_sector,
        "por_causal": por_causal,
        "matriz_sector_causal": matriz,
    }


# ---------------------------------------------------------------------------
# PARETO
# ---------------------------------------------------------------------------
def calc_pareto(df_eventos: pd.DataFrame, group_col: str = "causal") -> pd.DataFrame:
    if df_eventos.empty or group_col not in df_eventos.columns:
        return pd.DataFrame(columns=[group_col, "casos", "pct", "pct_acumulado"])
    agg = df_eventos.groupby(group_col, dropna=True)["cantidad"].sum().reset_index()
    agg = agg.rename(columns={"cantidad": "casos"})
    agg = agg.sort_values("casos", ascending=False).reset_index(drop=True)
    total = agg["casos"].sum()
    agg["pct"] = (100 * agg["casos"] / total).round(2) if total else 0
    agg["pct_acumulado"] = agg["pct"].cumsum().round(2)
    return agg


# ---------------------------------------------------------------------------
# EVOLUCIÓN TEMPORAL / AGRUPACIÓN DINÁMICA
# ---------------------------------------------------------------------------
def evolucion_por_agrupacion(df: pd.DataFrame, agrupacion_label: str, value_col="cantidad",
                              tipo_filter=None) -> pd.DataFrame:
    col = GROUP_LABELS.get(agrupacion_label, "fecha")
    data = df if tipo_filter is None else df[df["tipo_registro"] == tipo_filter]
    if data.empty or col not in data.columns:
        return pd.DataFrame(columns=[col, value_col])
    agg = data.groupby(col, dropna=True)[value_col].sum().reset_index()
    if col == "fecha":
        agg = agg.sort_values(col)
    return agg
