"""
charts.py
Constructores de gráficos Plotly reutilizados en la app y en la exportación
a Excel (vía kaleido -> PNG).

Diseño: paleta corporativa azul marino / naranjo, tipografía moderna,
y en los gráficos de composición (que traen 'pct_composicion' calculado
por analytics.calc_composicion) la barra representa el % real del total,
con el porcentaje arriba (azul marino) y el número de hallazgos dentro de
la barra (naranjo) -- así se ve de un vistazo la magnitud relativa Y el
volumen absoluto.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

TEMPLATE = "plotly_white"

# --- paleta corporativa -----------------------------------------------------
NAVY = "#0B2545"
NAVY_SOFT = "#13385E"
ORANGE = "#FF7A29"
ORANGE_SOFT = "#FFB27A"
GRID = "#E7ECF3"
TEXT_MUTED = "#5B6B82"
BG = "#FFFFFF"
FONT_FAMILY = "'Segoe UI', Inter, Arial, sans-serif"

# paleta secuencial azul marino -> naranjo para más de 2 categorías
NAVY_ORANGE_SCALE = [
    NAVY, "#28527A", "#4F7FA8", ORANGE_SOFT, ORANGE, "#E85D04",
]
COLOR_SEQ = [NAVY, ORANGE, "#4F7FA8", "#FFB27A", "#28527A", "#E85D04"]


def _base_layout(fig: go.Figure, titulo: str, subtitulo: str = None):
    title_text = f"<b>{titulo}</b>"
    if subtitulo:
        title_text += f"<br><span style='font-size:12px;color:{TEXT_MUTED}'>{subtitulo}</span>"
    fig.update_layout(
        title=dict(text=title_text, font=dict(size=18, color=NAVY, family=FONT_FAMILY), x=0.02, xanchor="left"),
        font=dict(family=FONT_FAMILY, color="#2B2B2B", size=12),
        plot_bgcolor=BG, paper_bgcolor=BG,
        margin=dict(t=70, l=50, r=30, b=60),
        hoverlabel=dict(bgcolor=NAVY, font_color="white", font_family=FONT_FAMILY),
    )
    return fig


def _fmt_int(v) -> str:
    try:
        return f"{int(round(v)):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def fig_evolucion(df_evol: pd.DataFrame, x_col: str, y_col: str, titulo: str) -> go.Figure:
    if df_evol.empty:
        return _empty_fig(titulo)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_evol[x_col], y=df_evol[y_col], mode="lines+markers",
        line=dict(color=NAVY, width=3, shape="spline"),
        marker=dict(size=7, color=ORANGE, line=dict(color=NAVY, width=1)),
        fill="tozeroy", fillcolor="rgba(11,37,69,0.06)",
        hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>",
    ))
    _base_layout(fig, titulo)
    fig.update_layout(
        xaxis=dict(title=x_col.capitalize(), showgrid=False, linecolor=GRID),
        yaxis=dict(title=y_col.capitalize(), showgrid=True, gridcolor=GRID, zeroline=False),
    )
    return fig


def fig_pareto(df_pareto: pd.DataFrame, group_col: str, titulo="Pareto de Defectos") -> go.Figure:
    if df_pareto.empty:
        return _empty_fig(titulo)
    total = df_pareto["casos"].sum()
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_pareto[group_col], y=df_pareto["casos"], name="Casos",
        marker=dict(color=NAVY),
        text=[f"<b>{_fmt_int(c)}</b>" for c in df_pareto["casos"]],
        textposition="outside", textfont=dict(color=NAVY, size=12),
        cliponaxis=False,
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} casos<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df_pareto[group_col], y=df_pareto["pct_acumulado"], name="% Acumulado",
        yaxis="y2", mode="lines+markers",
        line=dict(color=ORANGE, width=3), marker=dict(size=7, color=ORANGE),
        hovertemplate="<b>%{x}</b><br>%{y:.1f}% acumulado<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df_pareto[group_col], y=[80] * len(df_pareto), name="Referencia 80%",
        yaxis="y2", mode="lines", line=dict(color=TEXT_MUTED, dash="dash", width=1.5),
        hoverinfo="skip",
    ))
    _base_layout(fig, titulo, subtitulo=f"{_fmt_int(total)} casos totales")
    fig.update_layout(
        yaxis=dict(title="Casos", showgrid=True, gridcolor=GRID, zeroline=False),
        yaxis2=dict(title="% Acumulado", overlaying="y", side="right", range=[0, 105], showgrid=False),
        xaxis=dict(title=group_col.capitalize(), showgrid=False),
        legend=dict(orientation="h", y=-0.22, x=0.5, xanchor="center"),
        bargap=0.35,
    )
    return fig


def fig_composicion_pie(df_comp: pd.DataFrame, names_col: str, values_col: str, titulo: str) -> go.Figure:
    if df_comp.empty:
        return _empty_fig(titulo)
    total = df_comp[values_col].sum()
    n = len(df_comp)
    colors = COLOR_SEQ if n <= len(COLOR_SEQ) else NAVY_ORANGE_SCALE * (n // len(NAVY_ORANGE_SCALE) + 1)

    fig = go.Figure(go.Pie(
        labels=df_comp[names_col], values=df_comp[values_col], hole=0.62,
        marker=dict(colors=colors[:n], line=dict(color="white", width=2)),
        textinfo="percent", textfont=dict(size=13, color="white", family=FONT_FAMILY),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} (%{percent})<extra></extra>",
        sort=False,
    ))
    fig.add_annotation(
        text=f"<b style='font-size:22px;color:{NAVY}'>{_fmt_int(total)}</b><br>"
             f"<span style='font-size:11px;color:{TEXT_MUTED}'>total</span>",
        x=0.5, y=0.5, showarrow=False, font=dict(family=FONT_FAMILY),
    )
    _base_layout(fig, titulo)
    fig.update_layout(legend=dict(orientation="v", y=0.5, font=dict(size=12)))
    return fig


def fig_barras(df_agg: pd.DataFrame, x_col: str, y_col: str, titulo: str, orientation="v") -> go.Figure:
    if df_agg.empty:
        return _empty_fig(titulo)

    tiene_pct = "pct_composicion" in df_agg.columns
    df_agg = df_agg.sort_values(y_col, ascending=False).reset_index(drop=True)

    if tiene_pct:
        y_vals = df_agg["pct_composicion"]
        top_labels = [f"<b>{v:.1f}%</b>" for v in y_vals]
        hover = [
            f"<b>{cat}</b><br>{v:.1f}% del total<br>{_fmt_int(c)} hallazgos"
            for cat, v, c in zip(df_agg[x_col], y_vals, df_agg[y_col])
        ]
        y_title = "% del total"
    else:
        y_vals = df_agg[y_col]
        top_labels = [f"<b>{_fmt_int(v)}</b>" for v in y_vals]
        hover = [f"<b>{cat}</b><br>{_fmt_int(v)}" for cat, v in zip(df_agg[x_col], y_vals)]
        y_title = y_col.capitalize()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_agg[x_col], y=y_vals,
        marker=dict(color=NAVY, line=dict(width=0)),
        text=top_labels, textposition="outside",
        textfont=dict(color=NAVY, size=13, family=FONT_FAMILY),
        cliponaxis=False,
        hovertext=hover, hoverinfo="text",
    ))

    # etiqueta de "hallazgos" (conteo absoluto) DENTRO de cada barra, en blanco
    if tiene_pct:
        max_y = max(float(y_vals.max()), 1.0)
        for i in range(len(df_agg)):
            yv = float(y_vals.iloc[i])
            if yv <= 0:
                continue
            y_pos = max(yv * 0.5, max_y * 0.05)
            fig.add_annotation(
                x=df_agg[x_col].iloc[i], y=y_pos,
                text=f"<b>{_fmt_int(df_agg[y_col].iloc[i])}</b>",
                showarrow=False,
                font=dict(color="white", size=13, family=FONT_FAMILY),
            )

    _base_layout(fig, titulo, subtitulo="Barra: % del total  ·  Número: hallazgos" if tiene_pct else None)
    fig.update_layout(
        yaxis=dict(title=y_title, showgrid=True, gridcolor=GRID, zeroline=False,
                    ticksuffix="%" if tiene_pct else ""),
        xaxis=dict(title=x_col.capitalize(), showgrid=False),
        bargap=0.35,
    )
    return fig


def fig_heatmap_matriz(matriz: pd.DataFrame, titulo="Sector x Causal") -> go.Figure:
    if matriz is None or matriz.empty:
        return _empty_fig(titulo)
    fig = px.imshow(
        matriz, text_auto=True, color_continuous_scale=[[0, "#F3F6FA"], [0.5, ORANGE_SOFT], [1, NAVY]],
        aspect="auto",
    )
    fig.update_traces(hovertemplate="Sector: %{y}<br>Causal: %{x}<br>Casos: %{z}<extra></extra>")
    _base_layout(fig, titulo)
    fig.update_layout(xaxis_title="Causal", yaxis_title="Sector", coloraxis_colorbar=dict(title="Casos"))
    return fig


def fig_aceptabilidad_gauge(pct_aceptabilidad, titulo="% Aceptabilidad") -> go.Figure:
    val = pct_aceptabilidad if pct_aceptabilidad is not None else 0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number=dict(suffix="%", font=dict(color=NAVY, size=36, family=FONT_FAMILY)),
        gauge={
            "axis": {"range": [0, 100], "tickcolor": TEXT_MUTED},
            "bar": {"color": NAVY, "thickness": 0.35},
            "bgcolor": "white",
            "borderwidth": 0,
            "steps": [
                {"range": [0, 70], "color": "#FBE1D3"},
                {"range": [70, 90], "color": "#FFD9B0"},
                {"range": [90, 100], "color": "#CDEAD6"},
            ],
            "threshold": {"line": {"color": ORANGE, "width": 3}, "thickness": 0.9, "value": val},
        },
    ))
    _base_layout(fig, titulo)
    return fig


def _empty_fig(titulo: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=f"<b>{titulo}</b><br><span style='font-size:12px;color:{TEXT_MUTED}'>"
                         f"sin datos para los filtros seleccionados</span>",
                    font=dict(size=16, color=NAVY, family=FONT_FAMILY)),
        template=TEMPLATE, plot_bgcolor=BG, paper_bgcolor=BG,
        font=dict(family=FONT_FAMILY),
        xaxis={"visible": False}, yaxis={"visible": False},
        annotations=[{
            "text": "📭 Sin datos disponibles", "xref": "paper", "yref": "paper",
            "x": 0.5, "y": 0.5, "showarrow": False, "font": {"size": 15, "color": TEXT_MUTED},
        }],
    )
    return fig
