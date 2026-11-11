# Guía de estudio — entrevista BI (caso Meli / BigQuery)

**Para:** Julio Pradenas  
**Repo:** [JulioPradenas/meli-fulfillment-bq](https://github.com/JulioPradenas/meli-fulfillment-bq)  
**Uso:** preparar la defensa oral del portafolio (BI, modelo, calidad de datos, sandbox).  
**Alcance:** lab de portafolio. Marca con fines ilustrativos, estilo marketplace de fulfillment. **No** atribuir requisitos, SLAs ni datos a ningún empleador ni a Mercado Libre.

Números de abajo salen de `data/manifest.json`, `docs/paso-02-bronze.md`, `docs/paso-03-silver.md`, `docs/paso-04-gold.md` y `looker/STYLE_GUIDE.md` (seed 42). **No inventar.**

---

## 1) El proyecto en 2 minutos (pitch hablado)

> “Es un lab de fulfillment: la promesa de entrega, el tracking y el seller viven en exports distintos y el porcentaje de atraso se promedia mal. Armé un ELT en BigQuery sandbox (`GCP_PROJECT=meli-fulfillment-jp`, location US): CSV sintéticos seed 42, horizonte 2026-05-01 a 2026-10-31, bronze todo STRING, silver con cuarentena y gold en estrella. El hecho es `f_envios`, una fila por envío. A tiempo significa entregado y el día de entrega en America/Santiago es anterior o igual a `fecha_promesa`. Los porcentajes son SUM/SUM, nunca un promedio de porcentajes. Gold no parte por fecha: en el sandbox la partición vence a los 60 días según esa fecha y borraría mayo–octubre; uso `CLUSTER BY region_id, carrier_id`. Sin filtro, gold tiene 32.000 envíos, 24.335 entregados, 20.776 a tiempo y 3.559 atrasados. La RM atrasa 7,22% y los extremos 38,01%. Auth solo con ADC. El dashboard en Data Studio lo estoy armando yo; todavía no hay link público.”

Si preguntan “¿es producción?”: *lab operable de punta a punta con datos sintéticos. El contrato de grano y de métricas es el que engancharías a un export real.*

---

## 2) Recorrido paso a paso (1–4)

| Paso | Qué | Por qué | Cómo / artefactos | PR |
|---|---|---|---|---|
| **1** | Esqueleto, modelo y guía visual | Fijar grano, fórmulas y páginas antes de generar datos | [`docs/modelo-datos.md`](modelo-datos.md), [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md) | [#1](https://github.com/JulioPradenas/meli-fulfillment-bq/pull/1) |
| **2** | CSV + manifest + bronze | Contrato reproducible y landing que acepta basura | [`src/generate_data.py`](../src/generate_data.py), [`data/manifest.json`](../data/manifest.json), [`sql/ddl_bronze.sql`](../sql/ddl_bronze.sql), [`docs/paso-02-bronze.md`](paso-02-bronze.md). Seed **42** | [#2](https://github.com/JulioPradenas/meli-fulfillment-bq/pull/2) |
| **3** | Silver + cuarentena | Tipar y deduplicar sin perder filas | [`sql/silver/`](../sql/silver/), [`src/silver_rules.py`](../src/silver_rules.py), [`docs/paso-03-silver.md`](paso-03-silver.md). Incluye el fix de bronze todo STRING | [#3](https://github.com/JulioPradenas/meli-fulfillment-bq/pull/3) |
| **4** | Gold estrella | El dashboard lee aditivos, no re-define «a tiempo» | [`sql/gold/`](../sql/gold/), [`docs/paso-04-gold.md`](paso-04-gold.md). `f_envios` **32.000** | [#4](https://github.com/JulioPradenas/meli-fulfillment-bq/pull/4) |

**Entry point:** `make run` = generar CSV → load bronze (`WRITE_TRUNCATE`) → silver → gold → verify. Cada capa es `CREATE OR REPLACE` o un load job. Auth: `gcloud auth application-default login` y `export GCP_PROJECT=meli-fulfillment-jp`. No hay default de proyecto en el código.

El dashboard queda **pendiente**. El plan de páginas está en la guía de estilo; no hay viewer ni capturas.

---

## 3) Modelo y grano

El grano de la decisión es el **envío**, no la orden ni el evento de tracking. Una orden puede partirse en varios envíos; cada uno tiene su promesa.

| Objeto | 1 fila = | Dónde vive |
|---|---|---|
| `ordenes` | 1 orden (cabecera) | bronze / silver |
| `envios` | 1 envío, estado actual | bronze / silver |
| `eventos_tracking` | 1 hito de un envío | bronze / silver |
| `f_envios` | 1 envío que pasó silver | gold |
| `d_fecha` | 1 día (2026-05-01 → 2026-11-30) | gold, **214** días |
| `d_geografia` | 1 comuna, con región y `grupo_zona` | gold, **43** |
| `d_centro_fulfillment` | 1 centro | gold, **6** |
| `d_carrier` | 1 carrier | gold, **5** |
| `d_seller` | 1 seller | gold, **24** |

`grupo_zona` sale de los datos: `RM`; `extremos` = AP, AN, AI, MA; `centro` = zona centro sin la RM (VS, LI, ML); el resto se queda en `norte` o `sur`. No se mete todo en tres cubos.

Puente orden ↔ envío: `orden_id` en el hecho, dimensión degenerada. No cambia el grano.

---

## 4) Generador, seed y la historia

[`src/generate_data.py`](../src/generate_data.py). Seed **42**. Horizonte fijo **2026-05-01 → 2026-10-31** (`America/Santiago`). No usa `date.today()`, así que dos corridas dan el mismo CSV.

El núcleo limpio y las anomalías usan dos `Random(42)` distintos. Las anomalías son **filas extra**; el núcleo no se muta. El manifest cuenta cada tipo por tabla.

Historia sobre los **32.000** envíos limpios (los que llegan a silver y a gold), sin filtro:

| Corte | % atrasados | Entregados |
|---|---:|---:|
| RM | **0,0722** | **11.234** |
| Extremos AP+AN+AI+MA | **0,3801** | **2.223** |
| `CAR-ANDES` (Andes Express) | **0,0757** | **11.693** |
| `CAR-SUR` (Ruta Austral) | **0,3006** | **5.456** |
| `sin_stock_fc` | — | **853** cancelaciones; es la causa más grande |

Población gold sin filtro (misma definición, `verify_gold` OK): **24.335** entregados, **20.776** a tiempo, **3.559** atrasados, **2.218** cancelaciones logísticas. Hitos: creado **32.000** / despachado **28.470** / entregado **24.335**.

Nombres de sellers, carriers y centros son ficticios.

---

## 5) Bronze todo STRING — y el incidente real

Bronze es landing. **Todas** las columnas de [`sql/ddl_bronze.sql`](../sql/ddl_bronze.sql) son `STRING` y NULLABLE. El load es `WRITE_TRUNCATE`, schema explícito STRING, `max_bad_records=0`.

### Incidente (corrida real del PR #3, antes del fix)

El DDL tipaba `activo` como BOOL, `ts_creacion` y `ts_evento` como TIMESTAMP y `fecha_promesa` como DATE. BigQuery parsea el CSV contra ese tipo. Con `max_bad_records=0` el job aborta entero.

Mensaje: `Unable to parse; column_name: "activo" column_type: BOOL value: "NO-CAST"`.

Cargaron `regiones` (**18**) y `comunas` (**47**), que ya eran STRING. Fallaron las otras seis: centros, carriers, sellers, órdenes, envíos y eventos.

`make run DRY=1` no lo vio: validaba el header y contaba filas, no el valor contra el tipo del job.

**Qué no se hizo:** subir `max_bad_records`. Eso tira filas en silencio y rompe `bronze = silver + cuarentena`.

**Qué se hizo:** bronze todo STRING. Silver castea con `SAFE_CAST` desde `CAST(columna AS STRING)`. `activo` acepta `true` / `True` / `1` y `false` / `False` / `0`. `NO-CAST` entra a bronze y sale en cuarentena como `cast_fallido`.

Tests que cierran el hueco: `test_ddl_bronze_todas_las_columnas_son_string` y `test_csv_crudo_entra_en_schema_string_y_no_cast_revienta_un_tipo` en [`tests/test_paso02_bronze.py`](../tests/test_paso02_bronze.py).

### Conteos bronze (manifest `row_counts`, seed 42)

| Tabla | Bronze | Silver | Cuarentena |
|---|---:|---:|---:|
| `regiones` | 18 | 16 | 2 |
| `comunas` | 47 | 43 | 4 |
| `centros_fulfillment` | 11 | 6 | 5 |
| `carriers` | 9 | 5 | 4 |
| `sellers` | 31 | 24 | 7 |
| `ordenes` | 28.636 | 28.596 | 40 |
| `envios` | 32.064 | 32.000 | 64 |
| `eventos_tracking` | 151.595 | 151.524 | 71 |

La suma de las cuarentenas es **197** (2+4+5+4+7+40+64+71). Cada tabla cierra: bronze = silver + cuarentena. Lo verificó `verify_silver` en la corrida real (OK, 0 huérfanas en silver, los 30 motivos del reporte).

---

## 6) Silver: prioridad de motivos

Una fila de bronze termina en la tabla silver **o** en `q_<tabla>`, nunca en las dos y nunca en ninguna. Si tiene varios problemas, sale **una vez**, con el primer motivo de esta lista:

| Orden | Motivo | Cuándo |
|---|---|---|
| 1 | `cast_fallido` | Hay texto y `SAFE_CAST` devuelve NULL |
| 2 | `nulo_obligatorio` | Falta la PK o un campo requerido |
| 3 | `duplicado` | `ROW_NUMBER > 1` de la llave, entre las que pasaron 1 y 2 |
| 4 | `fk_huerfana` | El valor no está en la dimensión **silver** (el padre en cuarentena no alcanza) |
| 5 | `fecha_incoherente` | `ts_entrega < ts_despacho`, o un evento `entregado` anterior al despacho |

El cast va primero: si `activo = NO-CAST` y además falta la PK, el motivo es `cast_fallido`. Si no, la misma fila contaría dos veces y la ecuación no cierra.

Motivos distintos de cero (manifest `silver.tablas`, seed 42):

| Tabla | cast | nulo | duplicado | fk | fecha |
|---|---:|---:|---:|---:|---:|
| `regiones` | 0 | 1 | 1 | 0 | 0 |
| `comunas` | 0 | 1 | 1 | 2 | 0 |
| `centros_fulfillment` | 2 | 1 | 1 | 1 | 0 |
| `carriers` | 2 | 1 | 1 | 0 | 0 |
| `sellers` | 2 | 1 | 2 | 2 | 0 |
| `ordenes` | 4 | 14 | 10 | 12 | 0 |
| `envios` | 6 | 18 | 12 | 20 | 8 |
| `eventos_tracking` | 6 | 18 | 12 | 15 | 20 |

`nulo_obligatorio` junta clave vacía y fecha requerida vacía. Las 8 `fecha_incoherente` de envíos son filas inyectadas; las 20 de eventos son un `entregado` puesto 3 horas antes del despacho.

Dedup: `QUALIFY ROW_NUMBER()` por la llave natural. La copia exacta se queda una en silver.

---

## 7) Gold: estrella, cluster, sin partición

`f_envios` clusteriza por `region_id, carrier_id`. **No** hay `PARTITION BY`.

Por qué: en el sandbox la partición vence a los 60 días **según la fecha de la partición**, no según el día en que se creó la tabla. Con datos de mayo a octubre de 2026, partir por `fecha_promesa` borraría casi todo el hecho el mismo día del `CREATE`. El cluster no vence por fecha. La tabla entera igual expira a los 60 días de creada, y `make run` la reconstruye.

Gold no vuelve a limpiar. Las 32.000 filas de `f_envios` son las 32.000 de `meli_silver.envios`. `verify_gold` exige eso, 0 huérfanas contra cada dimensión, `envio_id` único, y la historia de la sección 4. La corrida real dio OK.

### A tiempo (definición cerrada)

```text
fecha_entrega = DATE(ts_entrega, 'America/Santiago')
es_entregado  = 1 si estado = 'entregado' y fecha_entrega no es nula
es_a_tiempo   = 1 si es_entregado = 1 y fecha_entrega <= fecha_promesa
es_atrasado   = 1 si es_entregado = 1 y fecha_entrega > fecha_promesa
```

El mismo día de la promesa es a tiempo. La hora dentro del día no cuenta. Por eso las dos flags suman `es_entregado`.

Lead time, solo en entregados, diferencia en minutos / 60:

```text
lead_time_orden_horas    = ts_entrega − ts_creacion
lead_time_despacho_horas = ts_entrega − ts_despacho
```

### Métricas SUM/SUM

Las vistas no guardan el porcentaje. Guardan conteos.

```text
cumplimiento de promesa = SUM(n_a_tiempo) / SUM(n_entregados)
% atrasados vs promesa   = SUM(n_atrasados) / SUM(n_entregados)
lead time orden          = SUM(suma_lead_time_orden_horas) / SUM(n_lead_time_orden)
participación de la causa = SUM(n_causa) del motivo / SUM(n_causa) del filtro
```

En el drill, los mismos ratios con `es_a_tiempo` y `es_entregado`. No marcar el 0/1 como tipo Porcentaje en la fuente: Looker lo promedia.

`v_causas_cancelacion` no repite el total de cancelados en cada fila. Un total repetido, al hacer `SUM`, se multiplica por la cantidad de motivos.

---

## 8) Sandbox, sin facturación

Proyecto de lab: `meli-fulfillment-jp`. Location: **US**. Datasets: `meli_bronze`, `meli_silver`, `meli_gold`.

| Permitido | No permitido |
|---|---|
| Load job `WRITE_TRUNCATE` | `INSERT` / `UPDATE` / `DELETE` / `MERGE` |
| `CREATE OR REPLACE TABLE` y `CREATE OR REPLACE VIEW` | Streaming inserts |
| Expiración de la tabla a 60 días desde el `CREATE` | Partición por fecha en este horizonte |
| ADC (`gcloud auth application-default login`) | JSON de service account en el repo |

`GCP_PROJECT` es obligatorio. Si falta, el script se detiene. No hay proyecto hardcodeado.

`make run` reconstruye CSV, bronze, silver y gold desde cero. No depende de lo que haya quedado de la corrida anterior, porque a los 60 días el sandbox borra las tablas.

---

## 9) Decisiones que hay que poder defender

1. **Grano envío, no orden.** La promesa es del envío. Una orden partida no tiene una sola fecha. `orden_id` queda en el hecho para el drill, sin cambiar el grano.
2. **Bronze STRING, silver estricto.** El landing no es el contrato. Tipar en el load convierte un problema de calidad en un job fallido (incidente `NO-CAST`). No subir `max_bad_records`.
3. **Un motivo por fila.** Si la misma fila entra dos veces a la cuarentena, `bronze = silver + cuarentena` no cierra. El cast gana al nulo, el nulo al duplicado, el duplicado a la FK, la FK a la fecha.
4. **FK contra silver, no contra bronze.** Un padre en cuarentena no alcanza para dar por bueno al hijo.
5. **Gold sin partición por fecha.** El sandbox vence la partición según su fecha. Cluster por `region_id` y `carrier_id`, que es el corte del dashboard.
6. **Porcentaje fuera de la vista.** Un `%` precalculado se promedia. Los aditivos se suman y el ratio se cierra al final del filtro.
7. **`grupo_zona` no aplasta el mapa.** RM y extremos son el corte de la historia. Norte y sur que no son extremos se quedan con su zona. No se inventan tres cubos que escondan Biobío o Tarapacá.
8. **Calendario hasta 2026-11-30.** La promesa de fines de octubre más el atraso cabe en noviembre. Si una fecha del hecho cae fuera, `verify_gold` la cuenta como huérfana.

---

## 10) Preguntas probables + respuesta modelo

1. **¿Qué problema resuelve?** Un SSoT de cumplimiento de promesa por envío: atraso, causa de cancelación logística y lead time, sin promediar porcentajes.
2. **¿Por qué medallón?** Bronze acepta el export. Silver decide si la fila sirve. Gold es lo que mira el dashboard. Looker no lee bronze.
3. **¿Por qué el grano es el envío?** Porque la promesa es del envío. La orden puede tener varios.
4. **¿Qué es a tiempo?** Entregado, y el día de entrega en `America/Santiago` es anterior o igual a `fecha_promesa`. No es «antes de las 21:00».
5. **¿Por qué SUM/SUM?** Un 10% sobre 20 envíos no pesa lo mismo que un 10% sobre 2.000. `AVG` de un porcentaje ya cerrado miente.
6. **¿7,22% contra 38,01%?** Es `SUM(es_atrasado)/SUM(es_entregado)`. RM: 11.234 entregados. Extremos AP/AN/AI/MA: 2.223. Mismos números en el generador y en `verify_gold`.
7. **¿Por qué bronze es STRING?** Porque BOOL/DATE/TIMESTAMP rechazaron `NO-CAST` y el job murió. `regiones` y `comunas` sí cargaron. El test nuevo compara cada valor del CSV con el tipo del schema.
8. **¿Por qué no subes `max_bad_records`?** Perderías filas sin motivo. La reconciliación dejaría de cerrar.
9. **¿Por qué DRY=1 no bastó?** Validaba headers y conteos, no el parseo del load. El fallo apareció en la corrida real.
10. **¿Por qué un solo motivo?** Para que cada fila de bronze esté en silver o en cuarentena, una vez. Prioridad: cast, nulo, duplicado, FK, fecha.
11. **¿197 cuarentenas?** Suma de las ocho tablas del manifest (2+4+5+4+7+40+64+71). Por tabla, bronze = silver + cuarentena. Corrida real: OK y 0 huérfanas en silver.
12. **¿Por qué la FK mira silver?** El seller también puede haber caído a cuarentena. Un hijo que apunta a ese padre no tiene dimensión.
13. **¿Por qué no particionas `f_envios`?** La partición del sandbox vence a los 60 días según su fecha. Mayo–octubre de 2026 ya está fuera. Cluster por región y carrier, que es el filtro del dashboard.
14. **¿Clustering ahorra bytes?** En este lab no hay demo de bytes. No inventar un porcentaje de prune. El cluster está para el corte del informe y para no borrar la historia.
15. **¿Por qué el calendario llega a noviembre?** Las entregas tardías de una promesa de octubre caen en noviembre. 214 días, del 2026-05-01 al 2026-11-30.
16. **¿CTAS o MERGE?** Sandbox sin DML. `CREATE OR REPLACE` y load `WRITE_TRUNCATE`. `make run` rehace todo. En prod, con billing, el mismo contrato puede pasar a MERGE del día.
17. **¿Dónde están las credenciales?** En ningún archivo. ADC en la laptop. CI solo corre pytest.
18. **¿Qué falta?** El dashboard publicado. Hay guía de estilo y vistas gold. No hay link ni capturas. No hay orquestación cloud. No hay claim sobre Mercado Libre ni sobre un empleador.

---

## 11) Incidentes y lecciones

### A) Load de bronze rechazó `NO-CAST` (PR #3, corrida real)

**Síntoma:** `make bronze` / `load_bronze.py` falló en seis tablas. OK solo `regiones` (18) y `comunas` (47).  
**Mensaje:** `Unable to parse; column_name: "activo" column_type: BOOL value: "NO-CAST"`. También estaban tipados `ts_creacion`, `ts_evento` (TIMESTAMP) y `fecha_promesa` (DATE).  
**Causa:** el load parsea contra el tipo de la columna. `max_bad_records=0` aborta el job. `DRY=1` no ejecuta ese parseo.  
**Fix:** bronze todo STRING NULLABLE. Silver hace `SAFE_CAST` desde STRING. Tests de DDL y de cada valor del CSV.  
**Lección:** el landing guarda el texto. La calidad se mide donde la fila todavía existe. No escondas el descarte en `max_bad_records`.

### B) No particionar gold (Paso 4, decisión)

**Riesgo evitado:** partir `f_envios` por `fecha_promesa` en el sandbox habría vencido las particiones de mayo a septiembre, y casi octubre, a los 60 días de esa fecha.  
**Decisión:** `CLUSTER BY region_id, carrier_id`. La tabla expira a los 60 días de creada y `make run` la regenera.  
**Lección:** no copies el patrón de partición de otro lab si la regla de vencimiento del sandbox se come el horizonte.

La corrida real de bronze, silver y gold, ya con bronze en STRING, dio OK: reconciliación, los 30 motivos, 0 huérfanas en silver, hecho = silver.envios, e historia de la sección 4.

---

## 12) Checklist de repaso

- [ ] Pitch de 2 minutos: problema, grano envío, medallón, SUM/SUM, sandbox, dashboard pendiente.
- [ ] Seed 42, horizonte 2026-05-01 → 2026-10-31, por qué no depende del día de hoy.
- [ ] Conteos bronze / silver / cuarentena de envíos: 32.064 / 32.000 / 64. Total cuarentena del lab: 197.
- [ ] Prioridad de motivos en orden: cast, nulo, duplicado, FK, fecha.
- [ ] Incidente `NO-CAST`: qué tablas cargaron, qué no, por qué DRY=1 no lo vio, por qué no se sube `max_bad_records`.
- [ ] Definición de a tiempo en una frase, y que las dos flags suman `es_entregado`.
- [ ] Números sin filtro: 24.335 / 20.776 / 3.559 / 2.218. RM 7,22% (11.234) contra extremos 38,01% (2.223). Andes 7,57% contra Ruta Austral 30,06%. `sin_stock_fc` 853.
- [ ] Por qué gold no tiene partición por fecha, y qué cluster sí tiene.
- [ ] Frase de sandbox: sin DML, solo `CREATE OR REPLACE` y load jobs, ADC, sin JSON en git.
- [ ] Decir en voz alta que el dashboard todavía no está publicado.

---

## Dashboard (pendiente)

Julio está armando el informe en Data Studio. **No hay viewer ni capturas** en el repo. No inventar un link.

Cuando exista, esta sección se completa con:

- Link público del reporte (share-as-reader).
- Capturas por página: Overview, atrasos, lead time, cancelaciones, embudo, drill.
- Valores leídos del informe publicado, comparados con la tabla de la sección 4 y con `looker/STYLE_GUIDE.md`. Si un número no calza, primero Restablecer filtros y confirmar que el campo es `SUM(n_a_tiempo)/SUM(n_entregados)` y no un `AVG`.

Hasta entonces, el plan de páginas, vistas y campos está en [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md), sección «Plan de armado sobre meli_gold». Las vistas que el informe debe usar son las de `meli_gold` listadas en la sección 7. Nada de bronze.

---

## Enlaces rápidos

| Recurso | Dónde |
|---|---|
| Modelo y grano | [`docs/modelo-datos.md`](modelo-datos.md) |
| Manifest (seed 42) | [`data/manifest.json`](../data/manifest.json) |
| Bronze e incidente STRING | [`docs/paso-02-bronze.md`](paso-02-bronze.md) |
| Silver y prioridad | [`docs/paso-03-silver.md`](paso-03-silver.md) |
| Gold, cluster, a tiempo | [`docs/paso-04-gold.md`](paso-04-gold.md) |
| Plan del dashboard | [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md) |
| Repo | https://github.com/JulioPradenas/meli-fulfillment-bq |
