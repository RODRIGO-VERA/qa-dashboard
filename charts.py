"""
charts.py
Constructores de gráficos Plotly reutilizados en la app y en la exportación
a Excel (vía kaleido -> PNG).
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

TEMPLATE = "plotly_white"
COLOR_SEQ = px.colors.qualitative.Set2


def fig_evolucion(df_evol: pd.DataFrame, x_col: str, y_col: str, titulo: str) -> go.Figure:
    if df_evol.empty:
        return _empty_fig(titulo)
    fig = px.line(df_evol, x=x_col, y=y_col, markers=True, template=TEMPLATE,
                   color_discrete_sequence=COLOR_SEQ)
    fig.update_layout(title=titulo, xaxis_title=x_col.capitalize(), yaxis_title=y_col.capitalize())
    return fig


def fig_pareto(df_pareto: pd.DataFrame, group_col: str, titulo="Pareto de Defectos") -> go.Figure:
    if df_pareto.empty:
        return _empty_fig(titulo)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_pareto[group_col], y=df_pareto["casos"], name="Casos",
        marker_color=COLOR_SEQ[0],
    ))
    fig.add_trace(go.Scatter(
        x=df_pareto[group_col], y=df_pareto["pct_acumulado"], name="% Acumulado",
        yaxis="y2", mode="lines+markers", line=dict(color="firebrick"),
    ))
    fig.add_trace(go.Scatter(
        x=df_pareto[group_col], y=[80] * len(df_pareto), name="Referencia 80%",
        yaxis="y2", mode="lines", line=dict(color="gray", dash="dash"),
    ))
    fig.update_layout(
        title=titulo, template=TEMPLATE,
        yaxis=dict(title="Casos"),
        yaxis2=dict(title="% Acumulado", overlaying="y", side="right", range=[0, 105]),
        xaxis=dict(title=group_col.capitalize()),
        legend=dict(orientation="h", y=-0.25),
    )
    return fig


def fig_composicion_pie(df_comp: pd.DataFrame, names_col: str, values_col: str, titulo: str) -> go.Figure:
    if df_comp.empty:
        return _empty_fig(titulo)
    fig = px.pie(df_comp, names=names_col, values=values_col, template=TEMPLATE,
                 color_discrete_sequence=COLOR_SEQ, hole=0.35)
    fig.update_layout(title=titulo)
    return fig


def fig_barras(df_agg: pd.DataFrame, x_col: str, y_col: str, titulo: str, orientation="v") -> go.Figure:
    if df_agg.empty:
        return _empty_fig(titulo)
    fig = px.bar(df_agg, x=x_col if orientation == "v" else y_col,
                 y=y_col if orientation == "v" else x_col,
                 orientation=orientation, template=TEMPLATE,
                 color_discrete_sequence=COLOR_SEQ, text_auto=".2s")
    fig.update_layout(title=titulo)
    return fig


def fig_heatmap_matriz(matriz: pd.DataFrame, titulo="Sector x Causal") -> go.Figure:
    if matriz is None or matriz.empty:
        return _empty_fig(titulo)
    fig = px.imshow(
        matriz, text_auto=True, template=TEMPLATE, color_continuous_scale="Blues",
        aspect="auto",
    )
    fig.update_layout(title=titulo, xaxis_title="Causal", yaxis_title="Sector")
    return fig


def fig_aceptabilidad_gauge(pct_aceptabilidad, titulo="% Aceptabilidad") -> go.Figure:
    val = pct_aceptabilidad if pct_aceptabilidad is not None else 0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        title={"text": titulo},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#2E7D32"},
            "steps": [
                {"range": [0, 70], "color": "#FFCDD2"},
                {"range": [70, 90], "color": "#FFF9C4"},
                {"range": [90, 100], "color": "#C8E6C9"},
            ],
        },
    ))
    fig.update_layout(template=TEMPLATE, title=titulo)
    return fig


def _empty_fig(titulo: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=f"{titulo} (sin datos para los filtros seleccionados)",
        template=TEMPLATE,
        xaxis={"visible": False}, yaxis={"visible": False},
        annotations=[{
            "text": "Sin datos disponibles", "xref": "paper", "yref": "paper",
            "showarrow": False, "font": {"size": 16},
        }],
    )
    return fig
