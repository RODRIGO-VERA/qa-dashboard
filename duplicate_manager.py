"""
duplicate_manager.py
Detección de duplicados a nivel de archivo (file_hash) y de registro
(row_hash), y clasificación de cada fila entrante como:
  - nuevo
  - duplicado_exacto
  - actualizado (misma llave natural, datos distintos)

IMPORTANTE: el row_hash se calcula DESPUÉS de la normalización (ver
data_cleaning.py), para que variantes de escritura no generen falsos
"nuevos".

SOBRE 'source_row_id' Y 'occ_idx' (fuentes SIN identificador único):
Algunas fuentes (ej. formularios Kobo/Forms) traen un ID de registro único
("ID del Formulario", "N° de Folio"); en ese caso se usa directamente como
identidad estable del registro -> dedup y detección de actualización 100%
confiables, incluso si el contenido cambia entre cargas.

Otras fuentes (ej. planillas históricas tipo "BD") NO traen ID por fila, y
pueden tener filas genuinamente distintas con contenido idéntico (dos cajas
distintas del mismo lote, mismo defecto, misma cantidad). Si solo se usara
el contenido normalizado como hash, esas filas colapsarían en una sola y se
perdería información real. Para esas filas, excel_processor calcula un
'occ_idx' (índice de ocurrencia: 0, 1, 2... entre las filas con contenido
idéntico dentro del mismo archivo) que se agrega al hash, preservando cada
fila como registro distinto sin dejar de detectar duplicados reales cuando
el mismo archivo (o una porción idéntica de él) se vuelve a cargar.
"""

import hashlib
import json
import pandas as pd

from config import KEY_FIELDS_FOR_AUDIT

# Columnas que participan en el row_hash (excluye metadatos de carga)
HASH_FIELDS = [
    "tipo_registro", "categoria_defecto", "fecha", "producto", "especie",
    "cliente", "lote", "turno", "linea", "maquina", "centro", "inspector",
    "causal", "sector", "cantidad", "unidades_inspeccionadas",
    "unidades_aceptadas", "unidades_rechazadas", "source_row_id", "occ_idx",
]

# Subconjunto que define la "llave natural" de un registro (para detectar
# que es "el mismo hecho" aunque algún dato se haya corregido/completado).
# Si el registro trae source_row_id (fuente con ID único), ESE es el único
# criterio de llave natural (ver compute_natural_key). Estos campos se usan
# solo como respaldo para fuentes sin ID único.
NATURAL_KEY_FIELDS = [
    "tipo_registro", "fecha", "producto", "lote", "turno", "linea",
    "causal", "sector", "occ_idx",
]


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def compute_import_key(file_bytes: bytes, sheet_name) -> str:
    """Identidad de UNA CARGA = archivo + hoja elegida. Distinto de
    compute_file_hash (que solo identifica el archivo): dos cargas del
    mismo archivo con hojas DISTINTAS deben poder procesarse ambas."""
    payload = compute_file_hash(file_bytes) + "::" + str(sheet_name)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _serialize_value(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    return str(v).strip().lower()


def compute_row_hash(row: dict) -> str:
    payload = {f: _serialize_value(row.get(f)) for f in HASH_FIELDS}
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def compute_natural_key(row: dict) -> dict:
    """Devuelve dict {columna: valor} usado para buscar si ya existe un
    registro 'equivalente' en la base, para poder detectar actualizaciones.

    Si la fila trae source_row_id (fuente con ID único por registro), la
    llave natural es EXCLUSIVAMENTE ese ID: es la identidad más confiable
    posible y evita falsos cruces por coincidencia de otros campos."""
    source_id = row.get("source_row_id")
    if source_id is not None and str(source_id).strip() != "":
        return {"source_row_id": str(source_id)}

    key = {}
    for f in NATURAL_KEY_FIELDS:
        v = row.get(f)
        if isinstance(v, pd.Timestamp):
            v = v.strftime("%Y-%m-%d")
        elif v is not None and not (isinstance(v, float) and pd.isna(v)):
            v = str(v)
        else:
            v = None
        key[f] = v
    return key


def diff_records(old: dict, new: dict, fields=None):
    """Compara dos dicts de registro y devuelve (hay_diferencias, campos_modificados,
    valores_anteriores, valores_nuevos)."""
    fields = fields or HASH_FIELDS
    modified = []
    before = {}
    after = {}
    for f in fields:
        ov = _serialize_value(old.get(f))
        nv = _serialize_value(new.get(f))
        if ov != nv:
            modified.append(f)
            before[f] = old.get(f)
            after[f] = new.get(f)
    return (len(modified) > 0), modified, before, after
