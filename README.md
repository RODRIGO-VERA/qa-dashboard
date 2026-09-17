# Dashboard de Aseguramiento de Calidad

Aplicación Streamlit para consolidar controles de producto terminado desde
múltiples Excel en una base histórica única (SQLite), sin duplicar
información, con analítica interactiva (Plotly) y exportación profesional
a Excel con gráficos embebidos.

## 1. Instalación

Requiere Python 3.10+.

```bash
cd qa_dashboard
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Paso único: habilitar exportación de gráficos a Excel

La librería `kaleido` (usada para convertir los gráficos Plotly en imágenes
PNG que se insertan en el Excel) necesita Google Chrome instalado. Ejecuta
**una sola vez**, con conexión a internet:

```bash
plotly_get_chrome
```

Si este paso no se ejecuta, la aplicación funciona igual, pero el Excel del
"Informe completo" incluirá una nota de texto en lugar del gráfico
correspondiente.

## 2. Ejecutar la aplicación

```bash
streamlit run app.py
```

Se abrirá en `http://localhost:8501`. La base de datos se crea
automáticamente en `data/database.db` y **persiste** entre sesiones
(no se borra al cerrar la app).

## 3. Flujo de uso

1. Ve a **Carga de Información** y sube uno o varios `.xlsx`.
2. Si el archivo tiene varias hojas, selecciona la hoja a procesar.
3. Presiona "Procesar". Verás el resumen:
   ```
   Archivo procesado: Semana_36.xlsx
   Registros leídos: 1.520
   Nuevos: 340
   Ya existentes: 1.170
   Actualizados: 7
   Con error: 3
   Base histórica: 25.460 registros
   ```
4. Navega a las pestañas analíticas (Resumen Ejecutivo, Aceptabilidad,
   Degradaciones, Pérdida de Vacío, Pareto, Explorador de Datos) y usa el
   panel de filtros en la barra lateral — están relacionados entre sí
   (cascada).
5. En **Exportación**, descarga la base filtrada o el informe completo:
   ambos respetan exactamente los filtros activos en ese momento.

## 4. Estructura de pestañas

El menú lateral tiene tres grupos:

- **📊 Vistas consolidadas** (Resumen Ejecutivo, Aceptabilidad, Degradaciones,
  Pérdida de Vacío, Pareto de Defectos, Explorador de Datos): combinan
  TODAS las fuentes cargadas en un solo análisis histórico, con filtros
  relacionados en cascada.
- **🧾 Vistas de detalle por fuente**: una pestaña dedicada por cada archivo/
  formulario reconocido automáticamente, mostrando sus columnas nativas y
  gráficos propios de ese origen, sin mezclarlo con las demás fuentes:
  - *Detalle · Pérdida de Vacío (Formulario)* — solo datos del formulario
    "Control - Producto sellado al vacío".
  - *Detalle · Degradación de Filete (Formulario)* — solo datos del
    formulario "Control de Calidad - Degradación de Filete", con el
    desglose Premium / Industrial A / Industrial B.
  - *Detalle · BD Histórico (Producto Terminado)* — solo datos de la hoja
    `BD` de la planilla histórica, con desglose por Calidad y Cliente.
- **⚙️ Administración** (Carga de Información, Historial de Importaciones,
  Exportación, **Respaldo y Restauración**).

### 🛡️ Respaldo y Restauración (importante para uso semanal en hosting gratuito)

Si vas a correr esta app en un hosting gratuito como Streamlit Community
Cloud, el almacenamiento puede reiniciarse tras un período de inactividad o
un redeploy, borrando `data/database.db`. La pestaña **Respaldo y
Restauración**:

- Descarga el archivo completo de la base de datos (`.db`) con un clic.
- Permite restaurar un respaldo previamente descargado, reemplazando la
  base actual (con confirmación explícita, y validación de que el archivo
  subido es realmente un respaldo válido de este dashboard antes de
  aplicarlo).

**Recomendación:** descarga un respaldo después de cada carga semanal y
guárdalo en tu computador o en la nube (Drive, OneDrive, etc.), con el
nombre que trae por defecto (incluye la fecha). Si alguna vez la base se
reinicia sola, restauras el último respaldo y sigues donde quedaste.

Cada pestaña de detalle tiene su propio panel de filtros (en cascada, igual
que las vistas consolidadas) y actualiza la selección disponible para
**Exportación**, de modo que puedes filtrar dentro de cualquiera de estas
pestañas y descargar exactamente esa selección.

## 5. Formatos de archivo reconocidos automáticamente

La aplicación detecta automáticamente 3 formatos de origen (ver
`source_adapters.py`) y transforma cada uno a un esquema largo común, sin
que tengas que ajustar nada manualmente:

| Formato detectado                                             | Se reconoce por                                              |
|-----------------------------------------------------------------|----------------------------------------------------------------|
| Control - Producto sellado al vacío (formulario)                | Título "Control - Producto sellado al vacio" en el archivo      |
| Control de Calidad - Degradación de Filete (formulario)         | Título "Degradación de Filete" en el archivo                    |
| Planilla histórica de producto terminado (hoja `BD`)            | Columnas `Defecto`, `Cantidad de cajas`, `Monitoreo` en la fila 1 |

Si subes un Excel que no coincide con ninguno de estos 3 formatos, la
aplicación usa el flujo genérico (homologación de columnas por
`config.COLUMN_ALIASES`, sección 7 más abajo) — útil para nuevas fuentes
que quieras agregar.

**Nota de calidad de datos detectada:** en el formulario de Pérdida de
Vacío, el campo llamado "Turno" contiene en la práctica el nombre del
supervisor, no un turno Día/Tarde/Noche. Por eso el adaptador no lo mapea
al campo `turno` (para no contaminar ese filtro) y lo guarda en
Observaciones. Si en tu sistema de captura esto se corrige, avisa para
ajustar `source_adapters.py`.

**Hojas del libro histórico que NO se ingieren automáticamente:** dentro
de `BD_Producto_terminado_2025.xlsx`, solo la hoja `BD` tiene un adaptador
dedicado. Hojas como `Tabla`, `Degradaciones A-B`, `BASE FILETE` o `BASE HG`
son tablas de análisis ya reprocesadas (con triplicación de filas por
lectura de temperatura) y no un log limpio de eventos — cargar esas hojas
como si fueran "genéricas" produciría conteos incorrectos. Si necesitas
incorporar su información histórica, mejor avísame para construir un
adaptador dedicado que las despliegue correctamente (sin triplicar).

## 6. Cómo funciona la deduplicación (crítico)

- **`file_hash`**: hash SHA-256 del archivo completo. Si subes el
  *mismo archivo, byte a byte*, una segunda vez, se detecta y se ignora
  por completo (no se reprocesa nada).
- **`row_hash`**: hash SHA-256 calculado **después de normalizar** cada
  fila (fecha, producto, turno, causal, sector, cantidades, etc.). Esto
  significa que "Hematoma", "hematoma" y "HEMATOMAS" generan el mismo
  row_hash tras pasar por `config.NORMALIZATION_DICTS`.
- Para cada fila del Excel entrante se evalúan tres casos:
  1. **row_hash ya existe** → registro idéntico → se ignora (duplicado).
  2. **No existe row_hash pero sí una fila con la misma "llave natural"**
     (fecha + producto + lote + turno + línea + causal/sector) con datos
     distintos → se **actualiza** el registro existente y se guarda el
     cambio en `historial_actualizaciones` (campo modificado, valor
     anterior, valor nuevo, archivo de origen).
  3. **No existe ni por row_hash ni por llave natural** → se inserta como
     **registro nuevo**.

Puedes revisar todo el detalle en la pestaña **Historial de
Importaciones** (incluye errores de importación y auditoría de cambios).

## 7. Ajustar la homologación a tus Excel reales

Los archivos de origen rara vez tienen nombres de columna 100% consistentes.
Edita `config.py`:

- `COLUMN_ALIASES`: agrega ahí cualquier variante de encabezado que uses
  en tus Excel (por ejemplo, si tu columna se llama "N° Lote Prod.",
  agrégala a la lista de `lote`).
- `NORMALIZATION_DICTS`: agrega variantes de texto (nombres de productos,
  causales, sectores, turnos) que deban homologarse a un único valor
  canónico.
- `DEGRADACION_PROPIA` / `DEGRADACION_NO_PROPIA`: ajusta la clasificación
  si tus causales de degradación difieren de las del pliego original.
- `SECTORES_VACIO` / `CAUSALES_VACIO`: ídem para pérdida de vacío.

No es necesario tocar ningún otro archivo para estos ajustes.

## 8. Cómo debe venir cada fila del Excel de origen

La aplicación es flexible respecto al layout, pero cada fila debe indicar,
como mínimo, a qué **tipo de registro** corresponde, en una columna que se
homologue a `tipo_registro` (o `categoria_defecto` — ver `COLUMN_ALIASES`)
con alguno de estos valores:

| tipo_registro     | Campos relevantes en esa fila                                  |
|-------------------|------------------------------------------------------------------|
| `inspeccion`      | unidades_inspeccionadas, unidades_aceptadas/rechazadas          |
| `defecto`         | causal, cantidad                                                |
| `degradacion`     | causal (debe estar en las listas propia/no propia), cantidad    |
| `perdida_vacio`   | sector, causal, cantidad                                        |

Todas las filas, sin importar el tipo, pueden traer además: fecha,
producto, especie, cliente, lote, turno, línea, máquina, centro, inspector.

Si tus Excel actuales no tienen esta columna de tipo, la forma más simple
es agregarla en origen (una columna extra) antes de cargar, o decirme el
formato exacto de tus archivos para adaptar `excel_processor.py` a tu caso
particular (por ejemplo, si "defectos" e "inspección" vienen en hojas
separadas, o si cada fila trae varias columnas de conteo por causal en
formato ancho en lugar de una fila por causal).

## 9. Arquitectura

```
app.py               Interfaz Streamlit (12 pestañas) y orquestación de UI
config.py             Rutas, homologación de columnas, diccionarios de normalización
database.py           Esquema SQLite y funciones de acceso a datos
data_cleaning.py       Normalización de texto y homologación de encabezados
duplicate_manager.py   file_hash, row_hash, llave natural, diff de registros
source_adapters.py     Detección y transformación de formatos de origen conocidos
excel_processor.py     Orquesta la carga: detección -> adaptador/homologación -> dedup -> inserción
analytics.py           KPIs, % incidencia vs % composición, Pareto, filtros en cascada
charts.py               Constructores de gráficos Plotly
filters.py              Panel de filtros dinámicos (sidebar)
excel_exporter.py       Exportación a Excel (base filtrada e informe completo con gráficos)
/data/database.db       Base de datos histórica (persistente, se crea sola)
/assets                 Recursos estáticos (logos, etc. si se agregan)
```

## 10. Notas sobre los porcentajes

- **% incidencia** = unidades afectadas / unidades inspeccionadas × 100
  (se usa en KPIs globales y en el detalle por causal de Degradaciones).
- **% composición** = casos de una causal / total de casos × 100
  (se usa en el Pareto y en los gráficos de distribución por causal/sector).

Ambos cálculos están separados explícitamente en `analytics.py`
(`calc_incidencia_por_grupo` vs `calc_composicion`) precisamente porque una
misma unidad puede tener más de un defecto, y mezclar ambas bases
distorsiona el análisis.
