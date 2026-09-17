"""
database.py
Capa de acceso a la base de datos histórica (SQLite).

Tablas:
- registros: tabla única que almacena tanto inspecciones como defectos/
  degradaciones/pérdidas de vacío (diferenciados por 'tipo_registro' y
  'categoria_defecto'). Se modela así para máxima flexibilidad ante
  estructuras de Excel heterogéneas, pero se exponen vistas/helpers
  llamados "inspecciones" y "defectos" tal como pide el requerimiento.
- importaciones: bitácora de cada archivo cargado.
- errores_importacion: filas que no pudieron incorporarse.
- historial_actualizaciones: auditoría de registros existentes que fueron
  actualizados por una carga posterior.
"""

import sqlite3
import os
import datetime
import pandas as pd
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row_hash TEXT UNIQUE NOT NULL,
    file_hash TEXT NOT NULL,
    source_format TEXT,
    source_row_id TEXT,
    occ_idx TEXT,
    tipo_registro TEXT,
    categoria_defecto TEXT,
    fecha TEXT,
    anio INTEGER,
    mes INTEGER,
    semana INTEGER,
    producto TEXT,
    especie TEXT,
    cliente TEXT,
    lote TEXT,
    turno TEXT,
    linea TEXT,
    maquina TEXT,
    centro TEXT,
    inspector TEXT,
    causal TEXT,
    sector TEXT,
    cantidad REAL,
    unidades_inspeccionadas REAL,
    unidades_aceptadas REAL,
    unidades_rechazadas REAL,
    observaciones TEXT,
    fecha_carga TEXT,
    nombre_archivo TEXT
);

CREATE TABLE IF NOT EXISTS importaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_archivo TEXT,
    file_hash TEXT,
    fecha_carga TEXT,
    hoja TEXT,
    filas_leidas INTEGER,
    registros_nuevos INTEGER,
    registros_duplicados INTEGER,
    registros_actualizados INTEGER,
    registros_error INTEGER,
    total_base_historica INTEGER
);

CREATE TABLE IF NOT EXISTS errores_importacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    importacion_id INTEGER,
    nombre_archivo TEXT,
    fila_excel INTEGER,
    motivo TEXT,
    datos_originales TEXT,
    fecha_carga TEXT
);

CREATE TABLE IF NOT EXISTS historial_actualizaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registro_id INTEGER,
    row_hash_anterior TEXT,
    row_hash_nuevo TEXT,
    campos_modificados TEXT,
    valores_anteriores TEXT,
    valores_nuevos TEXT,
    nombre_archivo TEXT,
    fecha_actualizacion TEXT
);

CREATE INDEX IF NOT EXISTS idx_registros_fecha ON registros(fecha);
CREATE INDEX IF NOT EXISTS idx_registros_producto ON registros(producto);
CREATE INDEX IF NOT EXISTS idx_registros_tipo ON registros(tipo_registro);
CREATE INDEX IF NOT EXISTS idx_registros_filehash ON registros(file_hash);
CREATE INDEX IF NOT EXISTS idx_registros_sourceid ON registros(source_row_id);
"""


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def file_already_processed(file_hash: str) -> bool:
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM importaciones WHERE file_hash = ?", (file_hash,)
        )
        return cur.fetchone()[0] > 0


def get_existing_row_hashes() -> set:
    with get_connection() as conn:
        cur = conn.execute("SELECT row_hash FROM registros")
        return {r[0] for r in cur.fetchall()}


def get_registro_by_natural_key(conn, natural_key_cols: dict):
    """Busca un registro existente por llave natural aproximada (sin usar
    row_hash), para poder detectar 'mismo registro con datos modificados'."""
    where_clauses = []
    params = []
    for col, val in natural_key_cols.items():
        if val is None:
            where_clauses.append(f"{col} IS NULL")
        else:
            where_clauses.append(f"{col} = ?")
            params.append(val)
    query = f"SELECT * FROM registros WHERE {' AND '.join(where_clauses)} LIMIT 1"
    cur = conn.execute(query, params)
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def insert_registro(conn, record: dict):
    cols = list(record.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    conn.execute(
        f"INSERT INTO registros ({col_names}) VALUES ({placeholders})",
        [record[c] for c in cols],
    )


def update_registro(conn, registro_id: int, record: dict):
    set_clause = ", ".join([f"{c} = ?" for c in record.keys()])
    params = list(record.values()) + [registro_id]
    conn.execute(f"UPDATE registros SET {set_clause} WHERE id = ?", params)


def log_importacion(conn, info: dict) -> int:
    cols = list(info.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cur = conn.execute(
        f"INSERT INTO importaciones ({col_names}) VALUES ({placeholders})",
        [info[c] for c in cols],
    )
    return cur.lastrowid


def log_error(conn, info: dict):
    cols = list(info.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    conn.execute(
        f"INSERT INTO errores_importacion ({col_names}) VALUES ({placeholders})",
        [info[c] for c in cols],
    )


def log_actualizacion(conn, info: dict):
    cols = list(info.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    conn.execute(
        f"INSERT INTO historial_actualizaciones ({col_names}) VALUES ({placeholders})",
        [info[c] for c in cols],
    )


def get_total_registros() -> int:
    with get_connection() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM registros")
        return cur.fetchone()[0]


def load_all_registros() -> pd.DataFrame:
    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM registros", conn)
    if len(df) and "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    return df


def load_importaciones() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM importaciones ORDER BY fecha_carga DESC", conn
        )


def load_errores() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM errores_importacion ORDER BY fecha_carga DESC", conn
        )


def load_historial_actualizaciones() -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM historial_actualizaciones ORDER BY fecha_actualizacion DESC",
            conn,
        )


# ---------------------------------------------------------------------------
# RESPALDO / RESTAURACIÓN
# Crítico en hosting gratuito (ej. Streamlit Community Cloud), donde el
# sistema de archivos puede reiniciarse tras inactividad o un redeploy,
# perdiendo data/database.db. Se recomienda descargar un respaldo después
# de cada carga semanal.
# ---------------------------------------------------------------------------
def export_db_bytes() -> bytes:
    """Lee el archivo físico de la base de datos completo, como bytes,
    para ofrecerlo como descarga de respaldo."""
    with open(DB_PATH, "rb") as f:
        return f.read()


def restore_db_from_bytes(data: bytes):
    """Sobrescribe la base de datos actual con un respaldo previamente
    descargado. Operación destructiva: reemplaza TODO el contenido actual."""
    import sqlite3 as _sqlite3

    tmp_path = DB_PATH + ".tmp_restore"
    with open(tmp_path, "wb") as f:
        f.write(data)

    # valida que el archivo subido sea realmente una base SQLite con el
    # esquema esperado antes de reemplazar la base actual
    test_conn = _sqlite3.connect(tmp_path)
    try:
        tablas = {
            r[0] for r in test_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        requeridas = {"registros", "importaciones", "errores_importacion", "historial_actualizaciones"}
        if not requeridas.issubset(tablas):
            raise ValueError(
                "El archivo no parece un respaldo válido de este dashboard "
                "(faltan tablas esperadas)."
            )
    finally:
        test_conn.close()

    os.replace(tmp_path, DB_PATH)


def get_db_info() -> dict:
    """Metadatos del archivo de base de datos actual (tamaño, última
    modificación), para mostrar en la pantalla de respaldo."""
    if not os.path.exists(DB_PATH):
        return {"existe": False}
    stat = os.stat(DB_PATH)
    return {
        "existe": True,
        "tamano_kb": round(stat.st_size / 1024, 1),
        "modificado": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }
