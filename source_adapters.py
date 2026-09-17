"""
source_adapters.py
Detección y transformación de formatos de archivo Excel REALES y conocidos,
al formato largo canónico que consume el resto del pipeline (una fila =
un evento: inspección, defecto, degradación o pérdida de vacío).

Formatos soportados:
  1. "forms_vacio"       -> exportación del formulario
                             "Control - Producto sellado al vacio"
  2. "forms_degradacion" -> exportación del formulario
                             "Control de Calidad - Degradación de Filete"
  3. "bd_historico"       -> hoja "BD" de planillas históricas tipo
                             BD_Producto_terminado_*.xlsx (log por caja)

Si ninguno de estos formatos coincide, excel_processor.py recurre al flujo
genérico (homologación de columnas por config.COLUMN_ALIASES).

Cada adaptador devuelve un DataFrame con columnas YA CANÓNICAS:
tipo_registro, categoria_defecto, fecha, producto, especie, cliente, lote,
turno, linea, maquina, centro, inspector, causal, sector, cantidad,
unidades_inspeccionadas, unidades_aceptadas, unidades_rechazadas,
observaciones, source_row_id
"""

import io
import re
import pandas as pd

from config import (
    TIPO_INSPECCION, TIPO_DEFECTO, TIPO_DEGRADACION, TIPO_PERDIDA_VACIO,
)

CANONICAL_COLS = [
    "tipo_registro", "categoria_defecto", "fecha", "producto", "especie",
    "cliente", "lote", "turno", "linea", "maquina", "centro", "inspector",
    "causal", "sector", "cantidad", "unidades_inspeccionadas",
    "unidades_aceptadas", "unidades_rechazadas", "observaciones",
    "source_row_id",
]


def _empty_record():
    return {c: None for c in CANONICAL_COLS}


def _to_num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        n = float(v)
        return n if n != 0 else 0.0
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# DETECCIÓN
# ---------------------------------------------------------------------------
def detect_format(file_bytes: bytes, sheet_name) -> dict:
    """Inspecciona las primeras filas crudas de la hoja para determinar el
    formato de origen. Devuelve {"formato": str, "header_row": int} o
    {"formato": "generico", "header_row": 0} si no coincide con ninguno."""
    raw = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=None, nrows=6)
    flat_text = " ".join(
        str(v) for v in raw.values.flatten() if v is not None and str(v) != "nan"
    ).lower()

    if "producto sellado al vacio" in flat_text:
        header_row = _find_header_row(raw, "id del formulario")
        return {"formato": "forms_vacio", "header_row": header_row}

    if "degradación de filete" in flat_text or "degradacion de filete" in flat_text:
        header_row = _find_header_row(raw, "id del formulario")
        return {"formato": "forms_degradacion", "header_row": header_row}

    # hoja "BD" histórica: se reconoce por firma de columnas en la fila 0
    header0 = [str(c).strip().lower() for c in raw.iloc[0].tolist()]
    firma_bd = {"defecto", "cantidad de cajas", "monitoreo"}
    if firma_bd.issubset(set(header0)):
        return {"formato": "bd_historico", "header_row": 0}

    return {"formato": "generico", "header_row": 0}


def _find_header_row(raw: pd.DataFrame, needle: str, default=3) -> int:
    for i in range(len(raw)):
        row_vals = [str(v).strip().lower() for v in raw.iloc[i].tolist()]
        if needle in row_vals:
            return i
    return default


# ---------------------------------------------------------------------------
# ADAPTADOR: Control - Producto sellado al vacio (Forms)
# ---------------------------------------------------------------------------
PV_CAUSAL_COLS = {
    "PV por mal sellado": "Mal Sellado",
    "PV por pliegue": "Pliegue",
    "PV por piquete": "Piquete",
    "PV por sello contaminado": "Sello Contaminado",
    "PV no determinado": "No Determinado",
}

AREA_TO_SECTOR = {
    "empaque": "Area Empaque",
    "post sellado": "Salida de Maquina",
    "post congelado": "Posterior al Congelado",
    "frigorifico": "Frigorifico",
}


def adapt_forms_vacio(df_raw: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in df_raw.iterrows():
        form_id = row.get("ID del Formulario")
        if pd.isna(form_id):
            continue
        form_id = str(int(form_id)) if isinstance(form_id, float) else str(form_id)

        fecha = row.get("Fecha de elaboracion")
        if pd.isna(fecha):
            fecha = row.get("Fecha")

        # NOTA DE CALIDAD DE DATOS: en este formulario, la columna "Turno"
        # contiene en la práctica nombres de supervisor (ej. "Daniel Soto"),
        # NO Día/Tarde/Noche -- a diferencia del formulario de Degradación,
        # donde sí es correcto. Para no contaminar el filtro de Turno del
        # dashboard con nombres de persona, se guarda en observaciones en
        # vez de en el campo 'turno'. Si en tu formulario real este campo
        # sí corresponde a un turno, avísame para revertir este mapeo.
        obs_parts = []
        if pd.notna(row.get("Area")):
            obs_parts.append(f"Area registro: {row.get('Area')}")
        if pd.notna(row.get("Turno")):
            obs_parts.append(f"Turno/Supervisor (campo original): {row.get('Turno')}")

        base = {
            "fecha": fecha,
            "producto": row.get("Producto"),
            "lote": row.get("Lote"),
            "turno": None,
            "maquina": row.get("Maquina"),
            "inspector": row.get("Monitor de calidad"),
            "observaciones": " | ".join(obs_parts) if obs_parts else None,
        }

        n_muestras = _to_num(row.get("N° de muestras"))
        insp = _empty_record()
        insp.update(base)
        insp["tipo_registro"] = TIPO_INSPECCION
        insp["unidades_inspeccionadas"] = n_muestras
        insp["source_row_id"] = f"vacio::{form_id}::insp"
        records.append(insp)

        sector = AREA_TO_SECTOR.get(str(row.get("Area")).strip().lower(), row.get("Area"))
        total_defectos = 0.0
        for col, causal in PV_CAUSAL_COLS.items():
            val = _to_num(row.get(col))
            if val and val > 0:
                total_defectos += val
                rec = _empty_record()
                rec.update(base)
                rec["tipo_registro"] = TIPO_PERDIDA_VACIO
                rec["sector"] = sector
                rec["causal"] = causal
                rec["cantidad"] = val
                rec["source_row_id"] = f"vacio::{form_id}::pv::{causal}"
                records.append(rec)

        if n_muestras is not None:
            insp["unidades_aceptadas"] = max(n_muestras - total_defectos, 0)
            insp["unidades_rechazadas"] = total_defectos

    return pd.DataFrame(records, columns=CANONICAL_COLS)


# ---------------------------------------------------------------------------
# ADAPTADOR: Control de Calidad - Degradación de Filete (Forms)
# ---------------------------------------------------------------------------
# columnas reales -> causal canónico, agrupadas por grado de calidad. Los
# nombres de "Industrial B" llegan duplicados por pandas con sufijo ".1" en
# las primeras 6, y con nombre propio "Cantidad de ..." en el resto.
DEGRAD_CAUSAL_MAP_A = {
    "Hematomas": "Hematoma", "Melanosis": "Melanosis", "Gaping": "Gapping",
    "Cracking": "Cracking", "Bajo Color": "Color", "Ancho de Grasa": "Ancho de Grasa",
    "Deformación": "Deformacion", "Color piel/Madurez": "Madurez",
    "Heridas externas": "Heridas Externas", "Cicatriz": "Cicatrices",
    "Escamas S-off/S-On": "Escamas", "Petequias": "Petequias", "Textura": "Textura",
    "Párasitos": "Parasitos", "Daño o corte mecánico": "Dano Mecanico",
}
DEGRAD_CAUSAL_MAP_B = {
    "Hematomas.1": "Hematoma", "Melanosis.1": "Melanosis", "Gaping.1": "Gapping",
    "Cracking.1": "Cracking", "Bajo Color.1": "Color", "Ancho de Grasa.1": "Ancho de Grasa",
    "Cantidad de Deformación": "Deformacion", "Cantidad de Color de Piel": "Madurez",
    "Cantidad de Heridas Externas": "Heridas Externas", "Cantidad de Cicatriz": "Cicatrices",
    "Cantidad de Escamas": "Escamas", "Cantidad de Petequias": "Petequias",
    "Cantidad de Textura": "Textura", "Cantidad de Parásitos": "Parasitos",
    "Cantidad de Daño o Corte Mecánico": "Dano Mecanico",
}


def adapt_forms_degradacion(df_raw: pd.DataFrame) -> pd.DataFrame:
    # 'Fecha' aparece duplicada (envío del formulario / fecha de control real);
    # pandas renombra la segunda ocurrencia a 'Fecha.1'.
    fecha_col = "Fecha.1" if "Fecha.1" in df_raw.columns else "Fecha"

    records = []
    for _, row in df_raw.iterrows():
        form_id = row.get("ID del Formulario")
        if pd.isna(form_id):
            continue
        form_id = str(int(form_id)) if isinstance(form_id, float) else str(form_id)

        jaula = row.get("Jaula")
        obs = f"Jaula: {jaula}" if pd.notna(jaula) else None
        temp = row.get("Temperatura en °C")
        if pd.notna(temp):
            obs = f"{obs + ' | ' if obs else ''}Temp: {temp}°C"

        base = {
            "fecha": row.get(fecha_col),
            "producto": row.get("Tipo de Producto"),
            "cliente": row.get("Cliente"),
            "turno": row.get("Turno"),
            "lote": row.get("LOTE"),
            "centro": row.get("Centro"),
            "inspector": row.get("Monitor"),
            "observaciones": obs,
        }

        cant_premium = _to_num(row.get("Cantidad Premium")) or 0.0
        total_a = 0.0
        total_b = 0.0

        degrad_records = []
        for col, causal in DEGRAD_CAUSAL_MAP_A.items():
            val = _to_num(row.get(col))
            if val and val > 0:
                total_a += val
                rec = _empty_record()
                rec.update(base)
                rec["tipo_registro"] = TIPO_DEGRADACION
                rec["categoria_defecto"] = "Industrial A"
                rec["causal"] = causal
                rec["cantidad"] = val
                rec["source_row_id"] = f"degrad::{form_id}::A::{causal}"
                degrad_records.append(rec)

        for col, causal in DEGRAD_CAUSAL_MAP_B.items():
            val = _to_num(row.get(col))
            if val and val > 0:
                total_b += val
                rec = _empty_record()
                rec.update(base)
                rec["tipo_registro"] = TIPO_DEGRADACION
                rec["categoria_defecto"] = "Industrial B"
                rec["causal"] = causal
                rec["cantidad"] = val
                rec["source_row_id"] = f"degrad::{form_id}::B::{causal}"
                degrad_records.append(rec)

        total_muestra = cant_premium + total_a + total_b
        insp = _empty_record()
        insp.update(base)
        insp["tipo_registro"] = TIPO_INSPECCION
        insp["unidades_inspeccionadas"] = total_muestra if total_muestra > 0 else None
        insp["unidades_aceptadas"] = cant_premium
        insp["source_row_id"] = f"degrad::{form_id}::insp"

        records.append(insp)
        records.extend(degrad_records)

    return pd.DataFrame(records, columns=CANONICAL_COLS)


# ---------------------------------------------------------------------------
# ADAPTADOR: hoja "BD" de planillas históricas (log por caja, sin ID único)
# ---------------------------------------------------------------------------
def adapt_bd_historico(df_raw: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, row in df_raw.iterrows():
        cajas = _to_num(row.get("Cantidad de cajas"))
        base = {
            "fecha": row.get("Fecha produccion"),
            "producto": row.get("Producto"),
            "cliente": row.get("Cliente"),
            "lote": row.get("Lote"),
            "linea": row.get("Tunel"),
        }
        defecto = row.get("Defecto")
        calidad = row.get("Calidad")
        monitoreo = str(row.get("Monitoreo") or "").strip().lower()
        es_sin_defecto = (
            defecto is None or (isinstance(defecto, float) and pd.isna(defecto))
            or str(defecto).strip().lower() in ("sin defecto", "nan", "")
        )

        insp = _empty_record()
        insp.update(base)
        insp["tipo_registro"] = TIPO_INSPECCION
        insp["categoria_defecto"] = calidad
        insp["unidades_inspeccionadas"] = cajas
        if monitoreo == "acepta":
            insp["unidades_aceptadas"] = cajas
        elif monitoreo == "rechaza":
            insp["unidades_rechazadas"] = cajas
        # sin source_row_id -> excel_processor calculará occ_idx (fila
        # ID-less; puede haber cajas distintas con exactamente los mismos
        # datos, y no deben colapsar en un solo registro).
        records.append(insp)

        if not es_sin_defecto:
            rec = _empty_record()
            rec.update(base)
            rec["tipo_registro"] = TIPO_DEFECTO
            rec["categoria_defecto"] = calidad
            rec["causal"] = defecto
            rec["cantidad"] = cajas
            records.append(rec)

    return pd.DataFrame(records, columns=CANONICAL_COLS)


ADAPTERS = {
    "forms_vacio": adapt_forms_vacio,
    "forms_degradacion": adapt_forms_degradacion,
    "bd_historico": adapt_bd_historico,
}

FORMAT_LABELS = {
    "forms_vacio": "Control - Producto sellado al vacío (formulario)",
    "forms_degradacion": "Control de Calidad - Degradación de Filete (formulario)",
    "bd_historico": "Planilla histórica de producto terminado (hoja BD)",
    "generico": "Formato genérico (homologación automática de columnas)",
}
