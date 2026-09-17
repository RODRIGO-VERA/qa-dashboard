"""
app.py
Dashboard de Aseguramiento de Calidad — aplicación principal Streamlit.

Pestañas:
  Resumen Ejecutivo | Aceptabilidad | Degradaciones | Pérdida de Vacío |
  Pareto de Defectos | Explorador de Datos | Carga de Información |
  Historial de Importaciones | Exportación
"""

import streamlit as st
import pandas as pd
import datetime

import database as db
import analytics
import charts
import filters as filt
import excel_processor
import excel_exporter
from config import TIPO_INSPECCION, TIPO_DEFECTO, TIPO_DEGRADACION, TIPO_PERDIDA_VACIO

st.set_page_config(
    page_title="Dashboard QA — Aseguramiento de Calidad",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded",
)

db.init_db()

# ---------------------------------------------------------------------------
# ESTILOS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    .main .block-container {padding-top: 1.5rem;}
    [data-testid="stMetric"] {
        background-color: #F5F8FC;
        border: 1px solid #E0E6ED;
        border-radius: 10px;
        padding: 12px 16px;
    }
    [data-testid="stMetricLabel"] {font-weight: 600; color: #1F4E78;}
    section[data-testid="stSidebar"] {background-color: #FAFBFD;}
    h1, h2, h3 {color: #1F4E78;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=5)
def load_data():
    return db.load_all_registros()


def refresh():
    load_data.clear()


# ---------------------------------------------------------------------------
# MENÚ LATERAL
# ---------------------------------------------------------------------------
st.sidebar.title("✅ Aseguramiento de Calidad")
st.sidebar.caption("Dashboard corporativo — control de producto terminado")

PAGES = [
    "📊 Resumen Ejecutivo", "📊 Aceptabilidad", "📊 Degradaciones", "📊 Pérdida de Vacío",
    "📊 Pareto de Defectos", "📊 Explorador de Datos",
    "🧾 Detalle · Pérdida de Vacío (Formulario)",
    "🧾 Detalle · Degradación de Filete (Formulario)",
    "🧾 Detalle · BD Histórico (Producto Terminado)",
    "⚙️ Carga de Información", "⚙️ Historial de Importaciones", "⚙️ Exportación",
    "🛡️ Respaldo y Restauración",
]
page = st.sidebar.radio("Navegación", PAGES, label_visibility="collapsed")
st.sidebar.divider()

df_all = load_data()
total_hist = len(df_all)
st.sidebar.metric("Registros en base histórica", f"{total_hist:,}".replace(",", "."))

ANALYTIC_PAGES = {
    "📊 Resumen Ejecutivo", "📊 Aceptabilidad", "📊 Degradaciones", "📊 Pérdida de Vacío",
    "📊 Pareto de Defectos", "📊 Explorador de Datos",
}

filtros_activos = {"selections": {}, "date_range": None}
df_filtered = df_all

if page in ANALYTIC_PAGES:
    filtros_activos = filt.render_filters(df_all, key_prefix="main")
    df_filtered = analytics.apply_filters(
        df_all, filtros_activos["selections"], filtros_activos["date_range"]
    )
    st.session_state["ultimo_df_filtrado"] = df_filtered
    st.session_state["ultimos_filtros"] = filtros_activos


# ---------------------------------------------------------------------------
# HELPERS DE UI
# ---------------------------------------------------------------------------
def fmt_pct(v):
    return f"{v:.1f}%" if v is not None else "N/D"


def fmt_num(v):
    if v is None or pd.isna(v):
        return "N/D"
    return f"{v:,.0f}".replace(",", ".")


def kpi_header(titulo):
    st.title(titulo)
    filtros_txt = excel_exporter._describe_filters(filtros_activos)
    st.caption(f"Filtros activos: {filtros_txt}")


# ---------------------------------------------------------------------------
# PÁGINA: RESUMEN EJECUTIVO
# ---------------------------------------------------------------------------
if page == "📊 Resumen Ejecutivo":
    kpi_header("📊 Resumen Ejecutivo")

    if df_filtered.empty:
        st.info("Aún no hay datos cargados. Ve a **Carga de Información** para subir tu primer Excel.")
    else:
        kpis = analytics.calc_kpis(df_filtered)

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Unidades inspeccionadas", fmt_num(kpis["total_inspeccionadas"]))
        c2.metric("% Aceptabilidad", fmt_pct(kpis["pct_aceptabilidad"]))
        c3.metric("% Defectuosidad", fmt_pct(kpis["pct_defectuosidad"]))
        c4.metric("% Degradación", fmt_pct(kpis["pct_degradacion"]))
        c5.metric("% Pérdida de vacío", fmt_pct(kpis["pct_perdida_vacio"]))

        c6, c7, c8, c9 = st.columns(4)
        c6.metric("Total de defectos", fmt_num(kpis["total_defectos"]))
        c7.metric("Principal causal defecto", kpis["principal_causal_defecto"] or "N/D")
        c8.metric("Principal causal degradación", kpis["principal_causal_degradacion"] or "N/D")
        c9.metric("Principal causal pérd. vacío", kpis["principal_causal_vacio"] or "N/D")

        st.divider()
        agrup = filt.render_agrupacion_selector("resumen")
        col1, col2 = st.columns(2)
        with col1:
            evol_def = analytics.evolucion_por_agrupacion(df_filtered, agrup, "cantidad", TIPO_DEFECTO)
            gcol = analytics.GROUP_LABELS.get(agrup, "fecha")
            st.plotly_chart(charts.fig_evolucion(evol_def, gcol, "cantidad",
                             f"Defectos por {agrup}"), use_container_width=True)
        with col2:
            defectos_df = df_filtered[df_filtered["tipo_registro"] == TIPO_DEFECTO]
            pareto = analytics.calc_pareto(defectos_df, "causal")
            st.plotly_chart(charts.fig_pareto(pareto.head(10), "causal",
                             "Top 10 causales — Pareto"), use_container_width=True)


# ---------------------------------------------------------------------------
# PÁGINA: ACEPTABILIDAD
# ---------------------------------------------------------------------------
elif page == "📊 Aceptabilidad":
    kpi_header("✔️ Aceptabilidad")

    if df_filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        kpis = analytics.calc_kpis(df_filtered)
        col1, col2 = st.columns([1, 2])
        with col1:
            st.plotly_chart(charts.fig_aceptabilidad_gauge(kpis["pct_aceptabilidad"]),
                             use_container_width=True)
        with col2:
            agrup = filt.render_agrupacion_selector("acept")
            gcol = analytics.GROUP_LABELS.get(agrup, "fecha")
            insp = df_filtered[df_filtered["tipo_registro"] == TIPO_INSPECCION]
            evol = insp.groupby(gcol, dropna=True).agg(
                unidades_inspeccionadas=("unidades_inspeccionadas", "sum"),
                unidades_aceptadas=("unidades_aceptadas", "sum"),
            ).reset_index()
            if not evol.empty:
                evol["pct_aceptabilidad"] = (
                    100 * evol["unidades_aceptadas"] / evol["unidades_inspeccionadas"]
                ).round(2)
            st.plotly_chart(
                charts.fig_evolucion(evol, gcol, "pct_aceptabilidad", f"% Aceptabilidad por {agrup}"),
                use_container_width=True,
            )
        st.divider()
        st.subheader("% Defectuosidad")
        st.caption("% incidencia = defectos / unidades inspeccionadas × 100")
        defect_evol = analytics.evolucion_por_agrupacion(df_filtered, "Semana", "cantidad", TIPO_DEFECTO)
        st.plotly_chart(charts.fig_evolucion(defect_evol, "semana", "cantidad",
                         "Evolución semanal de defectos"), use_container_width=True)


# ---------------------------------------------------------------------------
# PÁGINA: DEGRADACIONES
# ---------------------------------------------------------------------------
elif page == "📊 Degradaciones":
    kpi_header("🔍 Degradaciones")

    if df_filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        degrad = analytics.calc_degradaciones(df_filtered)
        detalle = degrad["detalle"]

        total = detalle["cantidad"].sum()
        propia = degrad["por_clase"].set_index("clase")["cantidad"].get("Propia", 0)
        no_propia = degrad["por_clase"].set_index("clase")["cantidad"].get("No Propia", 0)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total degradación (casos)", fmt_num(total))
        c2.metric("% Propia", fmt_pct(100 * propia / total if total else None))
        c3.metric("% No Propia", fmt_pct(100 * no_propia / total if total else None))

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(charts.fig_composicion_pie(degrad["por_clase"], "clase", "cantidad",
                             "Degradación propia vs no propia"), use_container_width=True)
        with col2:
            st.plotly_chart(charts.fig_barras(degrad["por_causal"], "causal", "cantidad",
                             "Degradación por causal (% composición)"), use_container_width=True)

        st.divider()
        agrup = filt.render_agrupacion_selector("degrad")
        gcol = analytics.GROUP_LABELS.get(agrup, "fecha")
        evol = analytics.evolucion_por_agrupacion(df_filtered, agrup, "cantidad", TIPO_DEGRADACION)
        st.plotly_chart(charts.fig_evolucion(evol, gcol, "cantidad", f"Evolución por {agrup}"),
                         use_container_width=True)

        st.subheader("Incidencia por causal")
        st.caption("% incidencia = unidades afectadas / unidades inspeccionadas × 100")
        insp = df_filtered[df_filtered["tipo_registro"] == TIPO_INSPECCION]
        inc = analytics.calc_incidencia_por_grupo(detalle, insp, "causal")
        st.dataframe(inc, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# PÁGINA: PÉRDIDA DE VACÍO
# ---------------------------------------------------------------------------
elif page == "📊 Pérdida de Vacío":
    kpi_header("💨 Pérdida de Vacío")

    if df_filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        vacio = analytics.calc_perdida_vacio(df_filtered)
        kpis = analytics.calc_kpis(df_filtered)

        c1, c2 = st.columns(2)
        c1.metric("% Pérdida de vacío global", fmt_pct(kpis["pct_perdida_vacio"]))
        c2.metric("Total casos", fmt_num(vacio["detalle"]["cantidad"].sum()))

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(charts.fig_barras(vacio["por_sector"], "sector", "cantidad",
                             "Presencia por sector"), use_container_width=True)
        with col2:
            st.plotly_chart(charts.fig_barras(vacio["por_causal"], "causal", "cantidad",
                             "% por causal"), use_container_width=True)

        st.subheader("Matriz Sector × Causal")
        st.plotly_chart(charts.fig_heatmap_matriz(vacio["matriz_sector_causal"]),
                         use_container_width=True)

        st.divider()
        agrup = filt.render_agrupacion_selector("vacio")
        gcol = analytics.GROUP_LABELS.get(agrup, "fecha")
        evol = analytics.evolucion_por_agrupacion(df_filtered, agrup, "cantidad", TIPO_PERDIDA_VACIO)
        st.plotly_chart(charts.fig_evolucion(evol, gcol, "cantidad", f"Evolución por {agrup}"),
                         use_container_width=True)


# ---------------------------------------------------------------------------
# PÁGINA: PARETO DE DEFECTOS
# ---------------------------------------------------------------------------
elif page == "📊 Pareto de Defectos":
    kpi_header("📈 Pareto de Defectos")

    if df_filtered.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        defectos_df = df_filtered[df_filtered["tipo_registro"] == TIPO_DEFECTO]
        pareto = analytics.calc_pareto(defectos_df, "causal")
        st.plotly_chart(charts.fig_pareto(pareto, "causal"), use_container_width=True)
        st.dataframe(pareto, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# PÁGINA: EXPLORADOR DE DATOS
# ---------------------------------------------------------------------------
elif page == "📊 Explorador de Datos":
    kpi_header("🗂️ Explorador de Datos")

    if df_all.empty:
        st.info("Aún no hay datos cargados.")
    else:
        st.caption(f"Total de filas en la base (según filtros activos): {len(df_filtered):,}".replace(",", "."))
        columnas = st.multiselect("Columnas a mostrar", list(df_filtered.columns),
                                   default=list(df_filtered.columns))
        busqueda = st.text_input("Buscar texto libre en toda la tabla")
        data = df_filtered[columnas] if columnas else df_filtered
        if busqueda:
            mask = data.astype(str).apply(lambda col: col.str.contains(busqueda, case=False, na=False))
            data = data[mask.any(axis=1)]
        st.dataframe(data, use_container_width=True, hide_index=True)
        st.caption(f"Mostrando {len(data):,} filas".replace(",", "."))


# ---------------------------------------------------------------------------
# PÁGINAS DE DETALLE POR FUENTE (una por archivo/formulario)
# ---------------------------------------------------------------------------
def _source_kpi_row(df_src: pd.DataFrame):
    kpis = analytics.calc_kpis(df_src)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unidades inspeccionadas", fmt_num(kpis["total_inspeccionadas"]))
    c2.metric("% Aceptabilidad", fmt_pct(kpis["pct_aceptabilidad"]))
    c3.metric("Total casos", fmt_num(kpis["total_defectos"] + (df_src[df_src["tipo_registro"] == TIPO_DEGRADACION]["cantidad"].sum() or 0) + (df_src[df_src["tipo_registro"] == TIPO_PERDIDA_VACIO]["cantidad"].sum() or 0)))
    c4.metric("Registros de esta fuente", fmt_num(len(df_src)))


if page == "🧾 Detalle · Pérdida de Vacío (Formulario)":
    st.title("🧾 Detalle · Pérdida de Vacío (Formulario)")
    st.caption("Datos provenientes exclusivamente del formulario **Control - Producto sellado al "
               "vacío**. Nota: el campo original «Turno» de este formulario en realidad contiene "
               "el nombre del supervisor, no un turno Día/Tarde/Noche — por eso no aparece como "
               "filtro de turno aquí; queda guardado en Observaciones.")

    df_src = df_all[df_all["source_format"] == "forms_vacio"] if "source_format" in df_all.columns else df_all.iloc[0:0]

    if df_src.empty:
        st.info("Aún no se ha cargado ningún archivo de este formulario. Ve a **Carga de Información**.")
    else:
        f_vacio = filt.render_filters(df_src, key_prefix="det_vacio")
        df_f = analytics.apply_filters(df_src, f_vacio["selections"], f_vacio["date_range"])
        st.session_state["ultimo_df_filtrado"] = df_f
        st.session_state["ultimos_filtros"] = f_vacio

        if df_f.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            _source_kpi_row(df_f)
            pv = df_f[df_f["tipo_registro"] == TIPO_PERDIDA_VACIO]

            col1, col2 = st.columns(2)
            with col1:
                por_area = analytics.calc_composicion(pv, "sector")
                st.plotly_chart(charts.fig_barras(por_area, "sector", "cantidad", "Casos por Área"),
                                 use_container_width=True)
            with col2:
                por_maquina = analytics.calc_composicion(pv, "maquina")
                st.plotly_chart(charts.fig_barras(por_maquina, "maquina", "cantidad", "Casos por Máquina"),
                                 use_container_width=True)

            pareto_pv = analytics.calc_pareto(pv, "causal")
            st.plotly_chart(charts.fig_pareto(pareto_pv, "causal", "Pareto — Causales de Pérdida de Vacío"),
                             use_container_width=True)

            evol = analytics.evolucion_por_agrupacion(df_f, "Semana", "cantidad", TIPO_PERDIDA_VACIO)
            st.plotly_chart(charts.fig_evolucion(evol, "semana", "cantidad", "Evolución semanal"),
                             use_container_width=True)

            st.subheader("Registros (Pérdida de Vacío)")
            tabla = pv[["fecha", "producto", "lote", "sector", "maquina", "causal", "cantidad",
                        "observaciones", "nombre_archivo"]].rename(columns={
                "fecha": "Fecha", "producto": "Producto", "lote": "Lote", "sector": "Área",
                "maquina": "Máquina", "causal": "Causal", "cantidad": "Cantidad",
                "observaciones": "Observaciones", "nombre_archivo": "Archivo origen",
            })
            st.dataframe(tabla, use_container_width=True, hide_index=True)


elif page == "🧾 Detalle · Degradación de Filete (Formulario)":
    st.title("🧾 Detalle · Degradación de Filete (Formulario)")
    st.caption("Datos provenientes exclusivamente del formulario **Control de Calidad - "
               "Degradación de Filete**. Distingue explícitamente Industrial A e Industrial B.")

    df_src = df_all[df_all["source_format"] == "forms_degradacion"] if "source_format" in df_all.columns else df_all.iloc[0:0]

    if df_src.empty:
        st.info("Aún no se ha cargado ningún archivo de este formulario. Ve a **Carga de Información**.")
    else:
        f_degrad = filt.render_filters(df_src, key_prefix="det_degrad")
        df_f = analytics.apply_filters(df_src, f_degrad["selections"], f_degrad["date_range"])
        st.session_state["ultimo_df_filtrado"] = df_f
        st.session_state["ultimos_filtros"] = f_degrad

        if df_f.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            _source_kpi_row(df_f)
            degrad_rows = df_f[df_f["tipo_registro"] == TIPO_DEGRADACION]
            insp_rows = df_f[df_f["tipo_registro"] == TIPO_INSPECCION]

            premium = insp_rows["unidades_aceptadas"].sum()
            ind_a = degrad_rows[degrad_rows["categoria_defecto"] == "Industrial A"]["cantidad"].sum()
            ind_b = degrad_rows[degrad_rows["categoria_defecto"] == "Industrial B"]["cantidad"].sum()
            grados_df = pd.DataFrame({
                "grado": ["Premium", "Industrial A", "Industrial B"],
                "cantidad": [premium, ind_a, ind_b],
            })

            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(charts.fig_composicion_pie(grados_df, "grado", "cantidad",
                                 "Distribución por grado de calidad"), use_container_width=True)
            with col2:
                por_causal = analytics.calc_composicion(degrad_rows, "causal")
                st.plotly_chart(charts.fig_barras(por_causal, "causal", "cantidad",
                                 "Causales de degradación (todos los grados)"), use_container_width=True)

            col3, col4 = st.columns(2)
            with col3:
                causal_a = analytics.calc_composicion(degrad_rows[degrad_rows["categoria_defecto"] == "Industrial A"], "causal")
                st.plotly_chart(charts.fig_barras(causal_a, "causal", "cantidad", "Causales — Industrial A"),
                                 use_container_width=True)
            with col4:
                causal_b = analytics.calc_composicion(degrad_rows[degrad_rows["categoria_defecto"] == "Industrial B"], "causal")
                st.plotly_chart(charts.fig_barras(causal_b, "causal", "cantidad", "Causales — Industrial B"),
                                 use_container_width=True)

            evol = analytics.evolucion_por_agrupacion(df_f, "Semana", "cantidad", TIPO_DEGRADACION)
            st.plotly_chart(charts.fig_evolucion(evol, "semana", "cantidad", "Evolución semanal"),
                             use_container_width=True)

            st.subheader("Registros (Degradación)")
            tabla = degrad_rows[["fecha", "producto", "cliente", "turno", "lote", "centro",
                                  "categoria_defecto", "causal", "cantidad", "observaciones",
                                  "nombre_archivo"]].rename(columns={
                "fecha": "Fecha", "producto": "Producto", "cliente": "Cliente", "turno": "Turno",
                "lote": "Lote", "centro": "Centro", "categoria_defecto": "Grado", "causal": "Causal",
                "cantidad": "Cantidad", "observaciones": "Observaciones", "nombre_archivo": "Archivo origen",
            })
            st.dataframe(tabla, use_container_width=True, hide_index=True)


elif page == "🧾 Detalle · BD Histórico (Producto Terminado)":
    st.title("🧾 Detalle · BD Histórico (Producto Terminado)")
    st.caption("Datos provenientes exclusivamente de la hoja **BD** de la planilla histórica "
               "de producto terminado (log a nivel de caja).")

    df_src = df_all[df_all["source_format"] == "bd_historico"] if "source_format" in df_all.columns else df_all.iloc[0:0]

    if df_src.empty:
        st.info("Aún no se ha cargado ningún archivo de este tipo. Ve a **Carga de Información**.")
    else:
        f_bd = filt.render_filters(df_src, key_prefix="det_bd")
        df_f = analytics.apply_filters(df_src, f_bd["selections"], f_bd["date_range"])
        st.session_state["ultimo_df_filtrado"] = df_f
        st.session_state["ultimos_filtros"] = f_bd

        if df_f.empty:
            st.info("No hay datos para los filtros seleccionados.")
        else:
            _source_kpi_row(df_f)
            defectos_bd = df_f[df_f["tipo_registro"] == TIPO_DEFECTO]

            col1, col2 = st.columns(2)
            with col1:
                por_calidad = analytics.calc_composicion(df_f[df_f["tipo_registro"] == TIPO_INSPECCION], "categoria_defecto")
                st.plotly_chart(charts.fig_composicion_pie(por_calidad, "categoria_defecto", "cantidad",
                                 "Distribución por Calidad"), use_container_width=True)
            with col2:
                por_cliente = analytics.calc_composicion(df_f, "cliente")
                st.plotly_chart(charts.fig_barras(por_cliente.head(10), "cliente", "cantidad",
                                 "Top clientes (por casos)"), use_container_width=True)

            pareto_bd = analytics.calc_pareto(defectos_bd, "causal")
            st.plotly_chart(charts.fig_pareto(pareto_bd, "causal", "Pareto — Causales de Defecto"),
                             use_container_width=True)

            agrup = filt.render_agrupacion_selector("det_bd")
            gcol = analytics.GROUP_LABELS.get(agrup, "fecha")
            evol = analytics.evolucion_por_agrupacion(df_f, agrup, "cantidad", TIPO_DEFECTO)
            st.plotly_chart(charts.fig_evolucion(evol, gcol, "cantidad", f"Defectos por {agrup}"),
                             use_container_width=True)

            st.subheader("Registros (Defectos)")
            tabla = defectos_bd[["fecha", "producto", "cliente", "lote", "linea",
                                  "categoria_defecto", "causal", "cantidad", "nombre_archivo"]].rename(columns={
                "fecha": "Fecha", "producto": "Producto", "cliente": "Cliente", "lote": "Lote",
                "linea": "Túnel/Línea", "categoria_defecto": "Calidad", "causal": "Defecto",
                "cantidad": "Cant. cajas", "nombre_archivo": "Archivo origen",
            })
            st.dataframe(tabla, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# PÁGINA: CARGA DE INFORMACIÓN
# ---------------------------------------------------------------------------
elif page == "⚙️ Carga de Información":
    st.title("📤 Carga de Información")
    st.caption("Sube uno o varios archivos Excel (.xlsx). Los registros nuevos se incorporarán "
               "a la base histórica; los duplicados se ignoran; los modificados se actualizan "
               "con trazabilidad.")

    uploaded_files = st.file_uploader(
        "Archivos Excel", type=["xlsx"], accept_multiple_files=True,
    )

    if uploaded_files:
        for uf in uploaded_files:
            st.markdown(f"#### 📄 {uf.name}")
            file_bytes = uf.getvalue()
            try:
                sheets = excel_processor.list_sheets(file_bytes)
            except Exception as e:
                st.error(f"No se pudo leer el archivo: {e}")
                continue

            if len(sheets) > 1:
                sheet_choice = st.selectbox(
                    f"Selecciona la hoja a procesar para «{uf.name}»", sheets,
                    key=f"sheet_{uf.name}",
                )
            else:
                sheet_choice = sheets[0]

            try:
                fmt_info = excel_processor.preview_format(file_bytes, sheet_choice)
                if fmt_info["formato"] == "generico":
                    st.warning(
                        "⚠️ No se reconoció un formato específico para esta hoja; se usará "
                        "homologación genérica de columnas (config.COLUMN_ALIASES). Revisa el "
                        "resultado en Explorador de Datos después de procesar."
                    )
                else:
                    st.info(f"✅ Formato detectado: **{fmt_info['etiqueta']}**")
            except Exception as e:
                st.warning(f"No se pudo detectar el formato automáticamente: {e}")

            if st.button(f"Procesar «{uf.name}» (hoja: {sheet_choice})", key=f"btn_{uf.name}"):
                with st.spinner("Procesando archivo..."):
                    resultado = excel_processor.process_uploaded_file(file_bytes, uf.name, sheet_choice)
                refresh()

                if resultado.get("ya_procesado"):
                    st.warning(resultado["mensaje"])
                else:
                    st.success(f"Archivo procesado correctamente ({resultado.get('formato_detectado', '')}).")
                    st.code(
                        f"Archivo procesado: {resultado['archivo']}\n"
                        f"Registros leídos: {resultado['filas_leidas']:,}\n"
                        f"Nuevos: {resultado['nuevos']:,}\n"
                        f"Ya existentes: {resultado['existentes']:,}\n"
                        f"Actualizados: {resultado['actualizados']:,}\n"
                        f"Con error: {resultado['con_error']:,}\n"
                        f"Base histórica: {resultado['base_historica']:,} registros".replace(",", "."),
                        language=None,
                    )


# ---------------------------------------------------------------------------
# PÁGINA: HISTORIAL DE IMPORTACIONES
# ---------------------------------------------------------------------------
elif page == "⚙️ Historial de Importaciones":
    st.title("🕓 Historial de Importaciones")

    df_imp = db.load_importaciones()
    if df_imp.empty:
        st.info("Aún no se ha procesado ningún archivo.")
    else:
        st.dataframe(df_imp, use_container_width=True, hide_index=True)

        st.subheader("¿Cargaste algo por error? Deshaz una importación puntual")
        st.caption(
            "Elimina SOLO los registros que entraron por una importación específica (por "
            "ejemplo, si elegiste la hoja equivocada). No afecta a las demás cargas."
        )
        opciones_import = {
            f"#{row.id} — {row.nombre_archivo} — {row.hoja} — {row.fecha_carga} "
            f"({row.registros_nuevos} nuevos)": row.id
            for row in df_imp.itertuples()
        }
        seleccion = st.selectbox("Importación a deshacer", list(opciones_import.keys()),
                                  index=None, placeholder="Elige una importación...")
        if seleccion:
            importacion_id = opciones_import[seleccion]
            confirmar_del = st.checkbox(
                "Confirmo que quiero eliminar los registros de esta importación.",
                key="confirmar_delete_import",
            )
            if st.button("🗑️ Eliminar esta importación", disabled=not confirmar_del):
                resultado = db.delete_import(importacion_id)
                refresh()
                if resultado["eliminado"]:
                    st.success(f"Se eliminaron {resultado['registros_eliminados']} registros de esa importación.")
                    st.rerun()
                else:
                    st.error(resultado["motivo"])

        st.subheader("Errores de importación")
        df_err = db.load_errores()
        if df_err.empty:
            st.caption("Sin errores registrados.")
        else:
            st.dataframe(df_err, use_container_width=True, hide_index=True)

        st.subheader("Auditoría de actualizaciones")
        df_upd = db.load_historial_actualizaciones()
        if df_upd.empty:
            st.caption("Sin actualizaciones registradas.")
        else:
            st.dataframe(df_upd, use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# PÁGINA: EXPORTACIÓN
# ---------------------------------------------------------------------------
elif page == "⚙️ Exportación":
    st.title("⬇️ Exportación")
    st.caption("La exportación corresponde exactamente a los filtros activos en la sesión "
               "(definidos en cualquiera de las pestañas analíticas).")

    df_export = st.session_state.get("ultimo_df_filtrado", df_all)
    filtros_export = st.session_state.get("ultimos_filtros", filtros_activos)

    st.write(f"Filtros activos: **{excel_exporter._describe_filters(filtros_export)}**")
    st.write(f"Filas a exportar: **{len(df_export):,}**".replace(",", "."))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Descargar base filtrada")
        st.caption("Solo los registros correspondientes a los filtros activos (una hoja).")
        if st.button("Generar Excel — Base filtrada"):
            data = excel_exporter.export_filtered_data(df_export)
            st.download_button(
                "📥 Descargar base_filtrada.xlsx", data=data,
                file_name=f"base_filtrada_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with col2:
        st.subheader("Descargar informe completo")
        st.caption("Excel profesional con Resumen Ejecutivo, Aceptabilidad, Degradaciones, "
                   "Pérdida de Vacío, Pareto, Base Filtrada e Historial — gráficos incluidos.")
        if st.button("Generar Excel — Informe completo"):
            with st.spinner("Generando informe (renderizando gráficos)..."):
                df_imp = db.load_importaciones()
                data = excel_exporter.export_full_report(df_export, df_imp, filtros_export)
            st.download_button(
                "📥 Descargar informe_completo.xlsx", data=data,
                file_name=f"informe_completo_{datetime.date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )


# ---------------------------------------------------------------------------
# PÁGINA: RESPALDO Y RESTAURACIÓN
# ---------------------------------------------------------------------------
elif page == "🛡️ Respaldo y Restauración":
    st.title("🛡️ Respaldo y Restauración")
    st.warning(
        "⚠️ **Importante si usas hosting gratuito (ej. Streamlit Community Cloud):** el "
        "almacenamiento puede reiniciarse si la app queda inactiva mucho tiempo o si haces "
        "un redeploy, y con eso se pierde `data/database.db`. Descarga un respaldo "
        "**después de cada carga semanal** y guárdalo en tu computador o en la nube "
        "(Drive, OneDrive, etc.). Si eso llega a pasar, puedes restaurar tu último respaldo "
        "aquí mismo en segundos."
    )

    info = db.get_db_info()
    if info.get("existe"):
        c1, c2, c3 = st.columns(3)
        c1.metric("Registros en la base actual", f"{db.get_total_registros():,}".replace(",", "."))
        c2.metric("Tamaño del archivo", f"{info['tamano_kb']:,} KB".replace(",", "."))
        c3.metric("Última modificación", info["modificado"])

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📥 Descargar respaldo")
        st.caption(
            "Descarga el archivo completo de la base de datos (`database.db`). Guárdalo con "
            "fecha, ej. `respaldo_2026-09-17.db`, para poder identificar el más reciente."
        )
        try:
            backup_bytes = db.export_db_bytes()
            st.download_button(
                "📥 Descargar respaldo (.db)", data=backup_bytes,
                file_name=f"respaldo_qa_dashboard_{datetime.date.today()}.db",
                mime="application/octet-stream",
            )
        except Exception as e:
            st.error(f"No se pudo generar el respaldo: {e}")

    with col2:
        st.subheader("📤 Restaurar desde un respaldo")
        st.caption(
            "⚠️ Esto **reemplaza por completo** la base de datos actual por la del archivo "
            "que subas. Úsalo solo si perdiste tu base (ej. tras un redeploy) y quieres "
            "recuperar el último respaldo guardado."
        )
        restore_file = st.file_uploader("Archivo de respaldo (.db)", type=["db"], key="restore_uploader")
        if restore_file is not None:
            confirmar = st.checkbox(
                "Entiendo que esto reemplazará TODOS los datos actuales por los del respaldo.",
                key="confirmar_restore",
            )
            if st.button("🔁 Restaurar base de datos", disabled=not confirmar, type="primary"):
                try:
                    db.restore_db_from_bytes(restore_file.getvalue())
                    refresh()
                    st.success("Base de datos restaurada correctamente. Recargando...")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo restaurar el respaldo: {e}")

    st.divider()
    st.subheader("🗑️ Borrar toda la base y empezar de cero")
    st.caption(
        "Elimina TODOS los registros de TODAS las fuentes, sin posibilidad de deshacerlo "
        "(salvo que tengas un respaldo descargado). Útil si quieres reiniciar completamente."
    )
    confirmar_reset = st.checkbox(
        "Entiendo que esto borra TODA la base de datos actual de forma permanente.",
        key="confirmar_reset_total",
    )
    if st.button("🗑️ Borrar TODO y empezar de cero", disabled=not confirmar_reset):
        db.reset_database()
        refresh()
        st.success("Base de datos vaciada. Puedes empezar a cargar tus archivos de nuevo.")
        st.rerun()
