"""
excel_exporter.py
Genera archivos Excel descargables:
  - export_filtered_data: solo los datos actualmente filtrados (una hoja).
  - export_full_report: informe profesional multi-hoja (Resumen Ejecutivo,
    Aceptabilidad, Degradaciones, Pérdida de Vacío, Pareto, Base Filtrada,
    Historial de Importaciones), con los gráficos Plotly insertados como
    imágenes (renderizados vía kaleido) -- no solo los datos.

Todo se calcula sobre el DataFrame YA FILTRADO que recibe la función, de
modo que el Excel exportado corresponde exactamente a la selección activa
en el dashboard en ese momento.
"""

import io
import xlsxwriter
import pandas as pd

import analytics
import charts

CHART_WIDTH = 900
CHART_HEIGHT = 500


def _fig_to_png_bytes(fig) -> bytes:
    return fig.to_image(format="png", width=CHART_WIDTH, height=CHART_HEIGHT, scale=2)


def export_filtered_data(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Base Filtrada", index=False)
        workbook = writer.book
        worksheet = writer.sheets["Base Filtrada"]
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#1F4E78", "font_color": "white"})
        for col_num, col_name in enumerate(df.columns):
            worksheet.write(0, col_num, col_name, header_fmt)
            worksheet.set_column(col_num, col_num, max(12, len(str(col_name)) + 2))
    output.seek(0)
    return output.read()


def export_full_report(df_filtered: pd.DataFrame, df_importaciones: pd.DataFrame,
                        filtros_activos: dict) -> bytes:
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})

    title_fmt = workbook.add_format({"bold": True, "font_size": 16, "font_color": "#1F4E78"})
    subtitle_fmt = workbook.add_format({"italic": True, "font_size": 10, "font_color": "#555555"})
    kpi_label_fmt = workbook.add_format({"bold": True, "bg_color": "#EEF3FA"})
    kpi_value_fmt = workbook.add_format({"font_size": 14, "bold": True, "font_color": "#1F4E78"})
    header_fmt = workbook.add_format({"bold": True, "bg_color": "#1F4E78", "font_color": "white"})

    # ---------------- Resumen Ejecutivo ----------------
    ws = workbook.add_worksheet("Resumen Ejecutivo")
    ws.write(0, 0, "Dashboard de Aseguramiento de Calidad — Resumen Ejecutivo", title_fmt)
    filtros_txt = _describe_filters(filtros_activos)
    ws.write(1, 0, f"Filtros activos: {filtros_txt}", subtitle_fmt)

    kpis = analytics.calc_kpis(df_filtered)
    kpi_rows = [
        ("Total unidades inspeccionadas", kpis["total_inspeccionadas"]),
        ("% Aceptabilidad global", kpis["pct_aceptabilidad"]),
        ("% Defectuosidad", kpis["pct_defectuosidad"]),
        ("% Degradación", kpis["pct_degradacion"]),
        ("% Pérdida de vacío", kpis["pct_perdida_vacio"]),
        ("Total de defectos", kpis["total_defectos"]),
        ("Principal causal defecto", kpis["principal_causal_defecto"]),
        ("Principal causal degradación", kpis["principal_causal_degradacion"]),
        ("Principal causal pérdida de vacío", kpis["principal_causal_vacio"]),
    ]
    row = 3
    for label, value in kpi_rows:
        ws.write(row, 0, label, kpi_label_fmt)
        ws.write(row, 1, value if value is not None else "N/D", kpi_value_fmt)
        row += 1

    evol = analytics.evolucion_por_agrupacion(df_filtered, "Semana", "cantidad")
    fig_evol = charts.fig_evolucion(evol, "semana", "cantidad", "Evolución de defectos por semana")
    _insert_chart(workbook, ws, fig_evol, row + 2, 0)

    # ---------------- Aceptabilidad ----------------
    ws2 = workbook.add_worksheet("Aceptabilidad")
    ws2.write(0, 0, "Aceptabilidad y Defectuosidad", title_fmt)
    fig_gauge = charts.fig_aceptabilidad_gauge(kpis["pct_aceptabilidad"])
    _insert_chart(workbook, ws2, fig_gauge, 2, 0)
    defect_evol = analytics.evolucion_por_agrupacion(df_filtered, "Semana", "cantidad",
                                                       tipo_filter="defecto")
    fig_defect = charts.fig_evolucion(defect_evol, "semana", "cantidad", "Defectuosidad — evolución")
    _insert_chart(workbook, ws2, fig_defect, 2, 10)

    # ---------------- Degradaciones ----------------
    ws3 = workbook.add_worksheet("Degradaciones")
    ws3.write(0, 0, "Degradaciones", title_fmt)
    degrad = analytics.calc_degradaciones(df_filtered)
    fig_clase = charts.fig_composicion_pie(degrad["por_clase"], "clase", "cantidad",
                                            "Degradación propia vs no propia")
    _insert_chart(workbook, ws3, fig_clase, 2, 0)
    fig_causal = charts.fig_barras(degrad["por_causal"], "causal", "cantidad",
                                    "Degradación por causal")
    _insert_chart(workbook, ws3, fig_causal, 2, 10)
    _write_dataframe(workbook, ws3, degrad["por_causal"], 30, 0, header_fmt)

    # ---------------- Pérdida de Vacío ----------------
    ws4 = workbook.add_worksheet("Pérdida de Vacío")
    ws4.write(0, 0, "Pérdida de Vacío", title_fmt)
    vacio = analytics.calc_perdida_vacio(df_filtered)
    fig_sector = charts.fig_barras(vacio["por_sector"], "sector", "cantidad",
                                    "Pérdida de vacío por sector")
    _insert_chart(workbook, ws4, fig_sector, 2, 0)
    fig_causal_v = charts.fig_barras(vacio["por_causal"], "causal", "cantidad",
                                      "Pérdida de vacío por causal")
    _insert_chart(workbook, ws4, fig_causal_v, 2, 10)
    fig_matriz = charts.fig_heatmap_matriz(vacio["matriz_sector_causal"])
    _insert_chart(workbook, ws4, fig_matriz, 30, 0)

    # ---------------- Pareto ----------------
    ws5 = workbook.add_worksheet("Pareto")
    ws5.write(0, 0, "Pareto de Defectos", title_fmt)
    defectos_df = df_filtered[df_filtered["tipo_registro"] == "defecto"]
    pareto = analytics.calc_pareto(defectos_df, "causal")
    fig_p = charts.fig_pareto(pareto, "causal")
    _insert_chart(workbook, ws5, fig_p, 2, 0)
    _write_dataframe(workbook, ws5, pareto, 30, 0, header_fmt)

    # ---------------- Base Filtrada ----------------
    ws6 = workbook.add_worksheet("Base Filtrada")
    _write_dataframe(workbook, ws6, df_filtered, 0, 0, header_fmt)

    # ---------------- Historial de Importaciones ----------------
    ws7 = workbook.add_worksheet("Historial de Importaciones")
    _write_dataframe(workbook, ws7, df_importaciones, 0, 0, header_fmt)

    workbook.close()
    output.seek(0)
    return output.read()


def _insert_chart(workbook, worksheet, fig, row, col):
    try:
        img_bytes = _fig_to_png_bytes(fig)
        worksheet.insert_image(row, col, "chart.png", {
            "image_data": io.BytesIO(img_bytes),
            "x_scale": 0.55, "y_scale": 0.55,
        })
    except Exception as e:
        worksheet.write(row, col, f"[No se pudo generar el gráfico: {e}]")


def _write_dataframe(workbook, worksheet, df, start_row, start_col, header_fmt):
    if df is None or df.empty:
        worksheet.write(start_row, start_col, "Sin datos para los filtros seleccionados")
        return
    df = df.reset_index() if df.index.name else df
    for j, col_name in enumerate(df.columns):
        worksheet.write(start_row, start_col + j, str(col_name), header_fmt)
        worksheet.set_column(start_col + j, start_col + j, max(12, len(str(col_name)) + 2))
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        for j, val in enumerate(r):
            if pd.isna(val):
                val = ""
            worksheet.write(start_row + i, start_col + j, val)


def _describe_filters(filtros: dict) -> str:
    parts = []
    selections = filtros.get("selections", {}) if filtros else {}
    for col, values in selections.items():
        if values:
            parts.append(f"{col}={','.join(map(str, values))}")
    date_range = filtros.get("date_range") if filtros else None
    if date_range:
        parts.append(f"fechas={date_range[0]}..{date_range[1]}")
    return "; ".join(parts) if parts else "Sin filtros (base histórica completa)"
