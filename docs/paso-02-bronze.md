# Paso 2 — CSV sintéticos y bronze en sandbox

> **Lab de portafolio. Marca con fines ilustrativos.**

**Proyecto GCP del lab:** `meli-fulfillment-jp` (solo por `GCP_PROJECT`; el código no lo asume).  
**Dataset:** `meli_bronze` · **location:** `US` · **expiración:** 60 días.  
**Semilla:** 42 · **horizonte:** 2026-05-01 → 2026-10-31 · **zona:** `America/Santiago`.

---

## Qué

Ocho CSV reproducibles (maestros de Chile + órdenes, envíos y eventos de tracking) y su carga a `meli_bronze`.

- `src/generate_data.py` escribe `data/raw/*.csv` y `data/manifest.json`.
- `sql/ddl_bronze.sql` + `src/apply_ddl.py` crean el dataset y reemplazan las tablas.
- `src/load_bronze.py` las llena con un load job.
- `make run` hace las tres cosas y compara `num_rows` contra el manifest.

El grano y las columnas salen de [modelo-datos.md](modelo-datos.md). Todas las columnas del DDL son **NULLABLE**.

## Por qué

El dashboard tiene que contar una historia antes de que exista gold: los atrasos pesan más en Arica, Antofagasta, Aysén y Magallanes que en la RM, el carrier ficticio Ruta Austral llega peor que Andes Express, y la cancelación logística más frecuente es `sin_stock_fc`.

Esa historia se rompe si el load rechaza los nulos. En KORA un schema `REQUIRED` devolvió `Required column value is missing` y las anomalías no entraron a bronze. Aquí el landing es permisivo a propósito: la cuarentena queda para silver.

El proyecto corre en **BigQuery sandbox, sin facturación**. Eso fija el diseño:

| Permitido | No permitido |
|---|---|
| Load job `WRITE_TRUNCATE` (`load_table_from_file`) | `INSERT` / `UPDATE` / `DELETE` / `MERGE` |
| `CREATE OR REPLACE TABLE` (schema) y, en silver/gold, `CREATE OR REPLACE TABLE/VIEW AS SELECT` | Streaming inserts (`insert_rows`) |
| Expiración de tablas y particiones a 60 días | Expiración más larga, o un `ALTER` para relajar `NOT NULL` |

No hay `ALTER`. Si el shape cambia, `CREATE OR REPLACE` deja la tabla vacía y el load la vuelve a llenar. Por el tope de 60 días del sandbox, **no se conserva el bronze entre semanas**: `make run` reconstruye CSV, tablas y filas desde cero. Lo mismo habrá que hacer con silver y gold (particiones incluidas: `partition_expiration_days = 60` y el dataset ya deja `default_partition_expiration_ms` en 60 días).

Location `US`: es el sandbox de este proyecto. Los datos son sintéticos y no hay requisito de dejarlos en Chile. La hora de negocio sigue siendo `America/Santiago` (el timestamp del CSV lleva el offset de ese huso).

Auth: Application Default Credentials. El repo no guarda llaves de service account. Si `GCP_PROJECT` no está exportado, el script termina y lo dice. No hay default.

## Cómo

En la Mac de Julio:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

gcloud auth application-default login
export GCP_PROJECT=meli-fulfillment-jp
make run
```

`make run` = `make data` + `make bronze` + verificación.

| Target | Qué hace |
|---|---|
| `make data` | Regenera CSV (seed 42) y `data/manifest.json`. Los CSV no se commitean. |
| `make bronze` | `CREATE OR REPLACE` de las 8 tablas y load `WRITE_TRUNCATE`. |
| `make run` | Lo anterior y una tabla manifest / csv / bq con `OK` o `FAIL`. |
| `make run DRY=1` | Regenera CSV, imprime el DDL y valida headers. No llama a BigQuery. |
| `make test` | pytest, sin ADC y sin red a GCP. |

El load usa schema explícito, `skip_leading_rows=1`, `autodetect=False`. Aunque el DDL ya es NULLABLE, el job vuelve a forzar `mode=NULLABLE` para no reintroducir `REQUIRED`.

### Conteos bronze (seed 42)

`row_counts` del manifest es lo que `num_rows` tiene que igualar. `clean_counts` es el núcleo antes de las filas extra.

| Tabla | Limpio | Bronze |
|---|---:|---:|
| `regiones` | 16 | 18 |
| `comunas` | 43 | 47 |
| `centros_fulfillment` | 6 | 9 |
| `carriers` | 5 | 7 |
| `sellers` | 24 | 29 |
| `ordenes` | 28.596 | 28.632 |
| `envios` | 32.000 | 32.050 |
| `eventos_tracking` | 151.524 | 151.589 |

Son decenas de miles de envíos y ~150 mil eventos: cabe en el sandbox y una query posterior sigue en el orden de centavos de dólar que el sandbox no cobra.

### Anomalías

Cada tipo es un número de **filas extra**. El núcleo limpio no se muta. `data/manifest.json` guarda el conteo por tabla. Los ceros también van, para que no haya un tipo “olvidado”.

| Tabla | FK huérfana | Fecha nula | Clave nula | Duplicado exacto | Entrega antes de despacho |
|---|---:|---:|---:|---:|---:|
| `regiones` | 0 | 0 | 1 | 1 | 0 |
| `comunas` | 2 | 0 | 1 | 1 | 0 |
| `centros_fulfillment` | 1 | 0 | 1 | 1 | 0 |
| `carriers` | 0 | 0 | 1 | 1 | 0 |
| `sellers` | 2 | 0 | 1 | 2 | 0 |
| `ordenes` | 12 | 8 | 6 | 10 | 0 |
| `envios` | 20 | 10 | 8 | 12 | 0 |
| `eventos_tracking` | 15 | 10 | 8 | 12 | 20 |

Centinelas de FK (no existen en el maestro): `SEL-HUERFANO`, `99999`, `FC-HUERFANO`, `CAR-HUERFANO`, `ORD-HUERFANA`, `ENV-HUERFANO`, `REG-HUERFANA`. La fecha nula vacía `ts_creacion` (órdenes), `fecha_promesa` (envíos) o `ts_evento` (tracking). La clave nula vacía la PK. El fuera de orden son 20 eventos `entregado` con timestamp 3 horas antes del `despachado` del mismo envío.

En el CSV el vacío es un campo en blanco. BigQuery lo carga como `NULL` porque la columna es NULLABLE.

### Historia que tiene que verse en el dashboard

Sobre los 32.000 envíos limpios (24.335 entregados), seed 42:

| Corte | % atrasados vs promesa | Entregados |
|---|---:|---:|
| Región Metropolitana | 7,22% | 11.234 |
| AP + AN + AI + MA | 38,01% | 2.223 |
| Andes Express (`CAR-ANDES`) | 7,57% | 11.693 |
| Ruta Austral (`CAR-SUR`) | 30,06% | 5.456 |

Cancelación logística: 2.218 envíos. `sin_stock_fc` es la causa más grande (853). Las otras cinco del catálogo también aparecen. El porcentaje de una causa, cuando se publique, es `SUM(cancelado_causa) / SUM(cancelado_logistica)`, no el promedio de porcentajes por FC.

Nombres de sellers, carriers y centros son ficticios.

### Silver y gold (todavía no)

Cuando se construyan, el mismo sandbox manda:

- Poblar con `CREATE OR REPLACE TABLE … AS SELECT` o `CREATE OR REPLACE VIEW … AS SELECT`. Nada de `MERGE`.
- Particionar si hace falta, con expiración de partición de 60 días.
- La estrictitud (PK, FK, orden de eventos, fechas) se aplica ahí, leyendo este manifest. Bronze se queda con la fila sucia.
- `make run` los reconstruye en la misma corrida. A los 60 días el sandbox los borra igual.

## Cómo se verificó

En este entorno **no hay credenciales GCP**. No se ejecutó el load real ni `apply_ddl` contra `meli-fulfillment-jp`.

Lo que sí corrió:

1. `make test` → **24 passed**. Cubre semilla estable (dos generaciones, y dos CSV byte a byte), columnas de cada tabla, manifest = anomalías contadas sobre las filas (no sobre el presupuesto a ciegas), la historia de atrasos, el DDL sin DML ni `NOT NULL`, el load job `WRITE_TRUNCATE` con schema NULLABLE, y el fallo claro si falta `GCP_PROJECT`.
2. `make run DRY=1` → los 8 statements `CREATE OR REPLACE`, headers válidos, y la tabla de conteos manifest = csv con `RESULTADO: OK (dry-run, sin BigQuery)`. La columna `bq` queda en `—` hasta que Julio corra `make run` con ADC.

Cuando eso pase en la Mac, la misma tabla tiene que mostrar el mismo número en manifest, csv y bq, y `RESULTADO: OK`. Si una tabla expiró a los 60 días, `make run` la vuelve a crear; no hace falta un backfill a mano.
