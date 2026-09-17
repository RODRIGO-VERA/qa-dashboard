"""
data_cleaning.py
Funciones de homologación de columnas y normalización de texto.
"""

import re
import unicodedata
import pandas as pd

from config import COLUMN_ALIASES, NORMALIZATION_DICTS


def _strip_accents(text: str) -> str:
    if not isinstance(text, str):
        return text
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_key(text: str) -> str:
    """Normaliza un string para usarlo como llave de comparación:
    minúsculas, sin tildes, espacios colapsados, sin caracteres especiales."""
    if text is None:
        return ""
    text = str(text)
    text = _strip_accents(text).lower().strip()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_text_value(text: str) -> str:
    """Normaliza un valor de texto para almacenamiento: sin tildes raras,
    capitalización tipo 'Titulo', espacios colapsados. Preserva mayúsculas
    de siglas cortas (<=3 letras)."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    if text == "":
        return None
    if len(text) <= 3:
        return text.upper()
    return text[0].upper() + text[1:]


def build_reverse_alias_map():
    """Construye un mapa {variante_normalizada: nombre_canonico} a partir de
    COLUMN_ALIASES para homologar encabezados de columnas."""
    reverse = {}
    for canonical, variants in COLUMN_ALIASES.items():
        reverse[normalize_key(canonical)] = canonical
        for v in variants:
            reverse[normalize_key(v)] = canonical
    return reverse


REVERSE_ALIAS_MAP = build_reverse_alias_map()


def homologate_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra las columnas del DataFrame a los nombres canónicos internos
    definidos en config.COLUMN_ALIASES. Columnas no reconocidas se conservan
    con su nombre original normalizado (para no perder información)."""
    new_columns = {}
    seen = set()
    for col in df.columns:
        key = normalize_key(col)
        canonical = REVERSE_ALIAS_MAP.get(key)
        if canonical is None:
            # columna desconocida: se conserva pero normalizada (snake-ish)
            canonical = re.sub(r"\s+", "_", key) if key else col
        # evitar colisiones de nombres duplicados
        final_name = canonical
        i = 2
        while final_name in seen:
            final_name = f"{canonical}_{i}"
            i += 1
        seen.add(final_name)
        new_columns[col] = final_name
    return df.rename(columns=new_columns)


def apply_normalization_dicts(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica los diccionarios de homologación de config.NORMALIZATION_DICTS
    sobre las columnas correspondientes (causal, sector, turno, producto,
    categoria_defecto), y aplica normalize_text_value al resto de columnas
    de texto conocidas."""
    df = df.copy()

    for col, mapping in NORMALIZATION_DICTS.items():
        if col in df.columns:
            def _map_value(v, mapping=mapping):
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return None
                key = normalize_key(v)
                if key in mapping:
                    return mapping[key]
                return normalize_text_value(v)
            df[col] = df[col].apply(_map_value)

    text_cols = [
        "producto", "especie", "cliente", "lote", "linea", "maquina",
        "centro", "inspector", "observaciones",
    ]
    for col in text_cols:
        if col in df.columns and col not in NORMALIZATION_DICTS:
            df[col] = df[col].apply(normalize_text_value)

    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)

    numeric_cols = [
        "cantidad", "unidades_inspeccionadas", "unidades_aceptadas",
        "unidades_rechazadas", "anio", "mes", "semana",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def derive_calendar_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Si existe columna 'fecha' válida, deriva anio/mes/semana cuando no
    vengan ya informados."""
    df = df.copy()
    if "fecha" in df.columns:
        valid = df["fecha"].notna()
        if "anio" not in df.columns:
            df["anio"] = pd.NA
        if "mes" not in df.columns:
            df["mes"] = pd.NA
        if "semana" not in df.columns:
            df["semana"] = pd.NA

        df.loc[valid & df["anio"].isna(), "anio"] = df.loc[valid, "fecha"].dt.year
        df.loc[valid & df["mes"].isna(), "mes"] = df.loc[valid, "fecha"].dt.month
        df.loc[valid & df["semana"].isna(), "semana"] = df.loc[valid, "fecha"].dt.isocalendar().week
    return df


def validate_dataframe(df: pd.DataFrame) -> (pd.DataFrame, pd.DataFrame):
    """Separa filas válidas de filas con error.
    Criterio mínimo de validez: al menos una columna de texto identificadora
    (producto/lote/causal) y, si existe categoria_defecto=defecto, que tenga
    causal informado. Devuelve (df_validas, df_errores)."""
    df = df.copy()
    df["_error_motivo"] = None

    if len(df) == 0:
        return df, df

    sin_identificacion = True
    for col in ["producto", "lote", "causal", "fecha"]:
        if col in df.columns:
            sin_identificacion = sin_identificacion & df[col].isna()
    df.loc[sin_identificacion, "_error_motivo"] = "Fila sin datos identificadores minimos"

    errores = df[df["_error_motivo"].notna()].copy()
    validas = df[df["_error_motivo"].isna()].copy()
    validas = validas.drop(columns=["_error_motivo"])
    return validas, errores
