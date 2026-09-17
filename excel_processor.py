"""
excel_processor.py
Orquesta el flujo completo de carga de un archivo Excel:
  1. Calcular file_hash y verificar si el archivo ya fue procesado.
  2. Detectar el formato de origen (source_adapters.detect_format) y leer
     la hoja con el encabezado correcto.
  3a. Si el formato es conocido (forms_vacio, forms_degradacion,
      bd_historico): transformarlo con su adaptador dedicado a formato
      largo canónico (ya trae source_row_id cuando la fuente tiene ID único).
  3b. Si no coincide con ningún formato conocido: homologar columnas
      genéricamente (config.COLUMN_ALIASES) — se asume ya formato largo
      (una fila = un evento).
  4. Normalizar texto/fechas.
  5. Para filas SIN source_row_id (fuentes sin identificador único), calcular
     un índice de ocurrencia (occ_idx) para no colapsar filas de contenido
     idéntico que representan hechos distintos (ver duplicate_manager.py).
  6. Validar filas (separar errores).
  7. Calcular row_hash y clasificar cada fila: nuevo / duplicado / actualizado.
  8. Insertar en la base histórica y registrar auditoría.
  9. Registrar el resumen de la importación.
"""

import io
import datetime
import json
import pandas as pd

import database as db
import source_adapters as sa
from data_cleaning import homologate_column_names, apply_normalization_dicts, derive_calendar_fields, validate_dataframe
from duplicate_manager import (
    compute_file_hash, compute_row_hash, compute_natural_key, diff_records,
)


def list_sheets(file_bytes: bytes):
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    return xls.sheet_names


def _read_raw(file_bytes: bytes, sheet_name, header_row: int) -> pd.DataFrame:
    return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name, header=header_row)


def preview_format(file_bytes: bytes, sheet_name) -> dict:
    """Detecta el formato de una hoja sin procesarla, para mostrarlo en la UI
    antes de confirmar la carga."""
    info = sa.detect_format(file_bytes, sheet_name)
    info["etiqueta"] = sa.FORMAT_LABELS.get(info["formato"], info["formato"])
    return info


def _add_occurrence_index(df: pd.DataFrame) -> pd.DataFrame:
    """Para filas sin source_row_id, agrega occ_idx = orden de aparición
    entre filas con los mismos campos IDENTIFICADORES (tipo_registro, fecha,
    producto, lote, turno, linea, causal, sector -- NO las cantidades),
    de modo que:
      - dos filas con los mismos identificadores pero distinta cantidad
        (dos cajas/eventos distintos del mismo lote) reciben occ_idx
        DIFERENTE -> se tratan como registros distintos, no se pisan entre sí;
      - si la misma fila (mismos identificadores Y misma cantidad) aparece
        dos veces en el archivo, se preserva como dos registros (occ_idx
        0 y 1), en vez de colapsar en uno solo y perder unidades;
      - al recargar el mismo archivo (u otro con las mismas filas), el
        orden de aparición se repite y el row_hash coincide -> se detecta
        como duplicado, tal como corresponde.
    """
    from duplicate_manager import NATURAL_KEY_FIELDS

    df = df.copy()
    if "occ_idx" not in df.columns:
        df["occ_idx"] = None
    if "source_row_id" not in df.columns:
        df["source_row_id"] = None

    sin_id_mask = df["source_row_id"].isna() | (df["source_row_id"].astype(str).str.strip() == "")
    if not sin_id_mask.any():
        return df

    identity_fields = [f for f in NATURAL_KEY_FIELDS if f not in ("occ_idx",) and f in df.columns]
    # fillna explícito: en pandas >= 2.x con dtype "str"/StringDtype, un NA
    # sobrevive a .astype(str) como valor nulo (no como texto "nan"), y
    # groupby() por defecto descarta esas filas (dropna=True), dejando
    # occ_idx en NaN silenciosamente. Se reemplaza el nulo por un centinela
    # de texto explícito antes de agrupar.
    sub = df.loc[sin_id_mask, identity_fields].astype(str).fillna("∅").replace("nan", "∅").replace("None", "∅").replace("NaT", "∅")
    df.loc[sin_id_mask, "occ_idx"] = sub.groupby(identity_fields, dropna=False).cumcount().astype(str)
    return df


def process_uploaded_file(file_bytes: bytes, filename: str, sheet_name) -> dict:
    """Procesa un archivo ya leído en bytes. Devuelve dict-resumen para
    mostrar en pantalla, con las llaves:
    archivo, filas_leidas, nuevos, existentes, actualizados, con_error,
    base_historica, ya_procesado (bool), formato_detectado
    """
    file_hash = compute_file_hash(file_bytes)
    fecha_carga = datetime.datetime.now().isoformat(timespec="seconds")

    if db.file_already_processed(file_hash):
        return {
            "archivo": filename,
            "ya_procesado": True,
            "mensaje": "Este archivo (idéntico byte a byte) ya fue cargado previamente. "
                       "No se realizaron cambios.",
        }

    formato_info = sa.detect_format(file_bytes, sheet_name)
    formato = formato_info["formato"]
    header_row = formato_info["header_row"]

    df_raw = _read_raw(file_bytes, sheet_name, header_row)
    filas_leidas = len(df_raw)

    if formato in sa.ADAPTERS:
        df = sa.ADAPTERS[formato](df_raw)
    else:
        df = homologate_column_names(df_raw)

    df = apply_normalization_dicts(df)
    df = derive_calendar_fields(df)
    df = _add_occurrence_index(df)
    df_validas, df_errores = validate_dataframe(df)

    nuevos = 0
    duplicados = 0
    actualizados = 0

    with db.get_connection() as conn:
        for _, row in df_validas.iterrows():
            record = row.to_dict()
            row_hash = compute_row_hash(record)

            cur = conn.execute("SELECT id FROM registros WHERE row_hash = ?", (row_hash,))
            existing_exact = cur.fetchone()
            if existing_exact is not None:
                duplicados += 1
                continue

            natural_key = compute_natural_key(record)
            existing = db.get_registro_by_natural_key(conn, natural_key)

            db_record = {
                "row_hash": row_hash,
                "file_hash": file_hash,
                "source_format": formato,
                "source_row_id": record.get("source_row_id"),
                "occ_idx": record.get("occ_idx"),
                "fecha_carga": fecha_carga,
                "nombre_archivo": filename,
            }
            for col in [
                "tipo_registro", "categoria_defecto", "producto", "especie",
                "cliente", "lote", "turno", "linea", "maquina", "centro",
                "inspector", "causal", "sector", "observaciones",
            ]:
                db_record[col] = record.get(col)

            fecha_val = record.get("fecha")
            db_record["fecha"] = (
                fecha_val.strftime("%Y-%m-%d")
                if pd.notna(fecha_val) and fecha_val is not None and hasattr(fecha_val, "strftime")
                else None
            )
            for col in ["anio", "mes", "semana", "cantidad", "unidades_inspeccionadas",
                        "unidades_aceptadas", "unidades_rechazadas"]:
                v = record.get(col)
                try:
                    db_record[col] = float(v) if v is not None and pd.notna(v) else None
                except (TypeError, ValueError):
                    db_record[col] = None

            if existing is not None:
                has_diff, modified, before, after = diff_records(existing, db_record)
                if has_diff:
                    db.update_registro(conn, existing["id"], db_record)
                    db.log_actualizacion(conn, {
                        "registro_id": existing["id"],
                        "row_hash_anterior": existing["row_hash"],
                        "row_hash_nuevo": row_hash,
                        "campos_modificados": json.dumps(modified, ensure_ascii=False),
                        "valores_anteriores": json.dumps(before, ensure_ascii=False, default=str),
                        "valores_nuevos": json.dumps(after, ensure_ascii=False, default=str),
                        "nombre_archivo": filename,
                        "fecha_actualizacion": fecha_carga,
                    })
                    actualizados += 1
                else:
                    duplicados += 1
                continue

            db.insert_registro(conn, db_record)
            nuevos += 1

        for idx, err_row in df_errores.iterrows():
            db.log_error(conn, {
                "importacion_id": None,
                "nombre_archivo": filename,
                "fila_excel": int(idx) + header_row + 2,
                "motivo": err_row.get("_error_motivo", "Error de validación"),
                "datos_originales": json.dumps(
                    {k: str(v) for k, v in err_row.to_dict().items()},
                    ensure_ascii=False,
                ),
                "fecha_carga": fecha_carga,
            })

        total_base = conn.execute("SELECT COUNT(*) FROM registros").fetchone()[0]

        importacion_id = db.log_importacion(conn, {
            "nombre_archivo": filename,
            "file_hash": file_hash,
            "fecha_carga": fecha_carga,
            "hoja": f"{sheet_name} ({sa.FORMAT_LABELS.get(formato, formato)})",
            "filas_leidas": filas_leidas,
            "registros_nuevos": nuevos,
            "registros_duplicados": duplicados,
            "registros_actualizados": actualizados,
            "registros_error": len(df_errores),
            "total_base_historica": total_base,
        })

    return {
        "archivo": filename,
        "ya_procesado": False,
        "formato_detectado": sa.FORMAT_LABELS.get(formato, formato),
        "filas_leidas": filas_leidas,
        "nuevos": nuevos,
        "existentes": duplicados,
        "actualizados": actualizados,
        "con_error": len(df_errores),
        "base_historica": total_base,
        "importacion_id": importacion_id,
    }
