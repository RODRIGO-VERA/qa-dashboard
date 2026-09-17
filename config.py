"""
config.py
Configuración central del Dashboard de Aseguramiento de Calidad.
Contiene rutas, homologación de nombres de columnas y diccionarios
de normalización de textos (productos, turnos, defectos, sectores, causales).

Estos diccionarios son el punto donde el usuario debe ajustar/ampliar
las variantes reales que aparezcan en sus archivos Excel.
"""

import os

# ---------------------------------------------------------------------------
# RUTAS
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "database.db")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# HOMOLOGACIÓN DE NOMBRES DE COLUMNAS
# Cada clave es el nombre canónico interno. Los valores son todas las
# variantes que pueden aparecer en los Excel de origen (minúsculas, sin
# tildes, sin espacios extra -- la comparación se normaliza antes de matchear).
# ---------------------------------------------------------------------------
COLUMN_ALIASES = {
    "fecha": ["fecha", "fecha inspeccion", "fecha control", "dia", "fecha_control"],
    "anio": ["anio", "ano", "year"],
    "mes": ["mes", "month"],
    "semana": ["semana", "sem", "week", "n semana", "numero semana"],
    "producto": ["producto", "especie producto", "item", "sku"],
    "especie": ["especie", "species"],
    "cliente": ["cliente", "customer"],
    "lote": ["lote", "lot", "batch", "n lote", "numero lote"],
    "turno": ["turno", "shift"],
    "linea": ["linea", "line", "n linea"],
    "maquina": ["maquina", "machine", "equipo"],
    "centro": ["centro", "origen", "centro origen", "planta", "sitio"],
    "inspector": ["inspector", "responsable", "controlador", "operador control"],
    "tipo_registro": ["tipo registro", "tipo", "categoria registro"],
    "categoria_defecto": [
        "categoria defecto", "tipo defecto", "clasificacion defecto",
        "categoria", "tipo de defecto",
    ],
    "causal": [
        "causal", "defecto", "causal defecto", "causa", "motivo",
        "detalle defecto", "descripcion defecto",
    ],
    "sector": [
        "sector", "area", "ubicacion", "sector deteccion",
        "lugar deteccion", "punto deteccion",
    ],
    "cantidad": [
        "cantidad", "n defectos", "numero defectos", "casos", "unidades afectadas",
        "unidades con defecto", "qty", "count",
    ],
    "unidades_inspeccionadas": [
        "unidades inspeccionadas", "muestras inspeccionadas", "total inspeccionado",
        "n muestras", "tamano muestra", "unidades muestreadas", "total muestra",
    ],
    "unidades_aceptadas": [
        "unidades aceptadas", "unidades ok", "unidades conformes", "aceptadas",
    ],
    "unidades_rechazadas": [
        "unidades rechazadas", "unidades no conformes", "rechazadas", "unidades nc",
    ],
    "observaciones": ["observaciones", "comentarios", "notas", "observacion"],
}

# Campos que identifican de forma "natural" un registro (se usan además del
# hash para trazabilidad, pero el hash es lo que decide duplicado/nuevo).
KEY_FIELDS_FOR_AUDIT = [
    "fecha", "producto", "lote", "turno", "linea", "causal", "sector",
]

# ---------------------------------------------------------------------------
# TIPOS DE REGISTRO SOPORTADOS (columna interna "tipo_registro")
# ---------------------------------------------------------------------------
TIPO_INSPECCION = "inspeccion"
TIPO_DEFECTO = "defecto"
TIPO_DEGRADACION = "degradacion"
TIPO_PERDIDA_VACIO = "perdida_vacio"

TIPOS_VALIDOS = [TIPO_INSPECCION, TIPO_DEFECTO, TIPO_DEGRADACION, TIPO_PERDIDA_VACIO]

# ---------------------------------------------------------------------------
# DEGRADACIONES
# Ampliado con los causales reales observados en los formularios de captura
# (Control de Calidad - Degradación de Filete) además de los del pliego original.
# ---------------------------------------------------------------------------
DEGRADACION_PROPIA = [
    "Melanosis", "Hematoma", "Cicatrices", "Descamacion", "Color", "Petequias",
    "Ancho de Grasa", "Deformacion", "Madurez", "Heridas Externas", "Escamas",
    "Parasitos", "Edema",
]
DEGRADACION_NO_PROPIA = [
    "Gapping", "Cracking", "Textura", "Dano Mecanico",
]

# ---------------------------------------------------------------------------
# PÉRDIDA DE VACÍO
# ---------------------------------------------------------------------------
SECTORES_VACIO = [
    "Area Empaque", "Salida de Maquina", "Posterior al Congelado", "Frigorifico",
]
CAUSALES_VACIO = [
    "Piquete", "Sello Contaminado", "Mal Sellado", "Pliegue", "No Determinado",
]

# Grados de calidad reales usados como "categoria_defecto" para degradación
# (Control de Calidad - Degradación de Filete separa Industrial A / Industrial B)
CALIDAD_GRADOS = ["Premium", "Industrial A", "Industrial B", "Maru"]

# ---------------------------------------------------------------------------
# DICCIONARIOS DE NORMALIZACIÓN DE TEXTO
# clave = texto normalizado (minúsculas, sin tildes) encontrado en el excel
# valor = texto canónico final que se guarda en la base de datos
# Se aplican con normalizacion "fuzzy" simple (ver data_cleaning.py) sobre
# minúsculas/sin tildes, por lo que basta con listar una vez cada variante.
# ---------------------------------------------------------------------------
NORMALIZATION_DICTS = {
    "causal": {
        "hematoma": "Hematoma",
        "hematomas": "Hematoma",
        "melanosis": "Melanosis",
        "cicatriz": "Cicatrices",
        "cicatrices": "Cicatrices",
        "heridas/cicatriz": "Cicatrices",
        "heridas externas": "Heridas Externas",
        "cantidad de heridas externas": "Heridas Externas",
        "descamacion": "Descamacion",
        "descamaciones": "Descamacion",
        "escamas s-off/s-on": "Escamas",
        "escamas s-off /s-onn": "Escamas",
        "cantidad de escamas": "Escamas",
        "color": "Color",
        "bajo color": "Color",
        "petequia": "Petequias",
        "petequias": "Petequias",
        "cantidad de petequias": "Petequias",
        "parasitos": "Parasitos",
        "parásitos": "Parasitos",
        "cantidad de parasitos": "Parasitos",
        "ancho de grasa": "Ancho de Grasa",
        "deformacion": "Deformacion",
        "deformación": "Deformacion",
        "cantidad de deformacion": "Deformacion",
        "color piel/madurez": "Madurez",
        "cantidad de color de piel": "Madurez",
        "madurez": "Madurez",
        "edema": "Edema",
        "gapping": "Gapping",
        "gaping": "Gapping",
        "cracking": "Cracking",
        "craking": "Cracking",
        "textura": "Textura",
        "cantidad de textura": "Textura",
        "dano mecanico": "Dano Mecanico",
        "danio mecanico": "Dano Mecanico",
        "dano o corte mecanico": "Dano Mecanico",
        "cantidad de dano o corte mecanico": "Dano Mecanico",
        "d. mecanico": "Dano Mecanico",
        "piquete": "Piquete",
        "piquetes": "Piquete",
        "pv por piquete": "Piquete",
        "sello contaminado": "Sello Contaminado",
        "pv por sello contaminado": "Sello Contaminado",
        "mal sellado": "Mal Sellado",
        "pv por mal sellado": "Mal Sellado",
        "pliegue": "Pliegue",
        "pliegues": "Pliegue",
        "pv por pliegue": "Pliegue",
        "no determinado": "No Determinado",
        "sin determinar": "No Determinado",
        "pv no determinado": "No Determinado",
        "temperatura": "Temperatura",
        "perdida de vacio": "Perdida de Vacio",
        "etiquetado": "Etiquetado",
        "sobre peso": "Sobre Peso",
        "bajo peso": "Bajo Peso",
        "punto de sangre": "Punto de Sangre",
        "puntos de sangre": "Punto de Sangre",
        "cantidad de piezas": "Cantidad de Piezas",
        "banda de grasa": "Banda de Grasa",
    },
    "sector": {
        "area empaque": "Area Empaque",
        "empaque": "Area Empaque",
        "salida de maquina": "Salida de Maquina",
        "salida maquina": "Salida de Maquina",
        "post sellado": "Salida de Maquina",
        "posterior al congelado": "Posterior al Congelado",
        "post congelado": "Posterior al Congelado",
        "frigorifico": "Frigorifico",
    },
    "turno": {
        "dia": "Dia",
        "turno dia": "Dia",
        "tarde": "Tarde",
        "turno tarde": "Tarde",
        "noche": "Noche",
        "turno noche": "Noche",
    },
    "producto": {
        # ejemplo: "coho" -> "Coho". Se completa según los productos reales.
        "coho": "Coho",
        "trucha": "Trucha",
        "atlantico": "Atlantico",
        "salmon atlantico": "Atlantico",
        "filete trim c": "Filete Trim C",
        "filete trim c s/off": "Filete Trim C S/Off",
        "harasu": "Harasu",
    },
    "categoria_defecto": {
        "defecto": TIPO_DEFECTO,
        "degradacion propia": "Degradacion Propia",
        "degradacion no propia": "Degradacion No Propia",
        "perdida de vacio": "Perdida de Vacio",
        "perdida vacio": "Perdida de Vacio",
        "premium": "Premium",
        "industrial a": "Industrial A",
        "industrial b": "Industrial B",
        "maru": "Maru",
    },
}
