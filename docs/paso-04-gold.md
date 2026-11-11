# Paso 4 — Gold en estrella, sin partición por fecha

> **Lab de portafolio. Marca con fines ilustrativos.**

**Dataset:** `meli_gold` · **location:** `US` · **expiración de la tabla:** 60 días desde que `make run` la crea.  
**Entrada:** solo `meli_silver`. La cuarentena no entra al hecho.  
**Hecho:** `f_envios`, 1 fila por envío. **32.000** filas, las mismas que `meli_silver.envios`.

---

## Qué

Un modelo estrella que Looker lee directo, con los conteos ya aditivos para que el porcentaje sea `SUM / SUM`.

| Tabla | Grano | Filas (seed 42) |
|---|---|---:|
| `d_fecha` | 1 día | 214 (2026-05-01 → 2026-11-30) |
| `d_geografia` | 1 comuna | 43 |
| `d_centro_fulfillment` | 1 centro | 6 |
| `d_carrier` | 1 carrier | 5 |
| `d_seller` | 1 seller | 24 |
| `f_envios` | 1 envío | 32.000 |

Vistas: `v_puntualidad_semana`, `v_lead_time`, `v_embudo_hitos`, `v_embudo_estado`, `v_causas_cancelacion`, `v_drill_envio`.

## Por qué no hay partición por fecha

En el sandbox la partición vence a los 60 días **según la fecha de la partición**, no según el día en que se creó la tabla. Hoy es 2026-11-11 y los envíos viven entre 2026-05-01 y 2026-10-31. Una `PARTITION BY fecha_promesa` borraría mayo, junio, julio, agosto y casi todo septiembre el mismo día del `CREATE`. Quedaría un hecho vacío con pinta de éxito.

`CLUSTER BY region_id, carrier_id` no vence por fecha. El dashboard filtra por región y carrier; el cluster sirve a ese corte. La tabla entera igual expira a los 60 días de creada, y `make run` la vuelve a armar. No es una demo de pruning: en este sandbox esa demo se come los datos.

## Por qué

Silver ya está limpio (32.000 envíos, 0 huérfanas). Gold no re-filtra: declara el grano, las dimensiones y los flags 0/1. Looker no debería castear ni redefinir «a tiempo» en cada gráfico.

## Cómo

`src/build_gold.py` corre `sql/gold/*.sql` en orden. `make gold` es ese paso. `make run` = data + bronze + silver + gold + las tres verificaciones. `DRY=1` no llama a BigQuery: `verify_gold` arma el mismo hecho en pandas.

### A tiempo

```text
fecha_entrega = DATE(ts_entrega, 'America/Santiago')
es_entregado  = 1 si estado = 'entregado' y fecha_entrega no es nula
es_a_tiempo   = 1 si es_entregado = 1 y fecha_entrega <= fecha_promesa
es_atrasado   = 1 si es_entregado = 1 y fecha_entrega > fecha_promesa
```

El mismo día de la promesa es a tiempo. La hora dentro del día no cuenta. Por eso `es_a_tiempo + es_atrasado = es_entregado` en todas las filas.

`es_cancelado_logistica = 1` si `estado = 'cancelado_logistica'`.

Lead time, solo en entregados, en horas con diferencia en minutos / 60 para que los tramos no se trunquen:

```text
lead_time_orden_horas    = (ts_entrega − ts_creacion) en horas
lead_time_despacho_horas = (ts_entrega − ts_despacho) en horas
```

### Dimensiones

`d_fecha` trae `semana_iso`, `anio_iso`, `lunes_semana` (el lunes de esa semana ISO) y `es_fin_de_semana`. El calendario llega hasta el 2026-11-30 porque una promesa de fines de octubre más el atraso cabe en noviembre. Si una fecha del hecho cayera fuera, `verify_gold` la contaría como huérfana.

`d_geografia` es la comuna con su región. `grupo_zona` sale de los datos, no de un mapa inventado de tres cubos:

| grupo_zona | Quién |
|---|---|
| `RM` | región RM |
| `extremos` | AP, AN, AI, MA (el corte de la historia) |
| `centro` | zona centro sin la RM: VS, LI, ML |
| `norte` | el norte que no es extremo: TA, AT, CO |
| `sur` | NB, BI, AR, LR, LL |

### Vistas y fórmulas

Ninguna vista guarda el porcentaje. Guardan numerador y denominador.

| Vista | Grano | Campos aditivos | Fórmula en Looker |
|---|---|---|---|
| `v_puntualidad_semana` | región × carrier × lunes de `fecha_promesa` | `n_envios`, `n_entregados`, `n_a_tiempo`, `n_atrasados`, `n_cancelado_logistica` | `SUM(n_a_tiempo) / SUM(n_entregados)` |
| `v_lead_time` | región × carrier × lunes de la promesa | `suma_lead_time_orden_horas`, `n_lead_time_orden`, y el par de despacho | `SUM(suma_lead_time_orden_horas) / SUM(n_lead_time_orden)` |
| `v_embudo_hitos` | hito | `n_envios` | el conteo, no un % |
| `v_embudo_estado` | estado final | `n_envios` | el conteo |
| `v_causas_cancelacion` | motivo × región × centro | `n_causa` | `SUM(n_causa)` del motivo / `SUM(n_causa)` del filtro |
| `v_drill_envio` | envío | flags 0/1 y fechas **DATE** | `SUM(es_a_tiempo) / SUM(es_entregado)` |

`v_causas_cancelacion` no repite el total de cancelados en cada fila. Un total repetido, al hacer `SUM`, se multiplica por la cantidad de motivos y el denominador miente.

### Historia que verify_gold exige

Sobre `f_envios`, sin filtro, redondeo a 4 decimales. Son los mismos números del generador porque silver se quedó con el núcleo limpio y gold no tira filas.

| Corte | % atrasados | Entregados |
|---|---:|---:|
| RM | 0,0722 | 11.234 |
| extremos AP+AN+AI+MA | 0,3801 | 2.223 |
| `CAR-ANDES` | 0,0757 | 11.693 |
| `CAR-SUR` | 0,3006 | 5.456 |
| `sin_stock_fc` | — | 853 cancelaciones, la causa más grande |

Si un número no calza, no se edita el esperado. Se explica qué definición cambió.

## Cómo se verificó

Sin credenciales GCP. No se creó `meli_gold` en BigQuery.

- `make test` incluye `tests/test_paso04_gold.py`: el SQL no tiene `PARTITION BY`, `f_envios` clusteriza por `region_id, carrier_id`, las vistas exponen `n_a_tiempo` y `n_entregados`, y el hecho pandas cierra la historia.
- `make run DRY=1` termina con `verify_gold` en `RESULTADO: OK`.

## Cómo defenderlo en una entrevista

- **¿Por qué no particionas el hecho?** Porque en este sandbox la partición muere a los 60 días de *su* fecha. El dato ya es más viejo que eso. Cluster por las columnas del filtro (`region_id`, `carrier_id`) y una tabla que se reconstruye entera. Particionar aquí sería perder el dashboard, no ahorrar bytes.
- **¿Por qué el porcentaje no está en la vista?** Porque un porcentaje precalculado se promedia. `n_a_tiempo` y `n_entregados` se suman y el % se cierra al final del filtro.
- **¿Qué es a tiempo?** Entregado, y el día de la entrega en Santiago es anterior o igual al día prometido. No es «llegó antes de las 21:00».
- **¿Gold vuelve a limpiar?** No. La cuarentena ya se quedó en silver. Gold tiene las mismas 32.000 filas. Si no, la reconciliación con silver falla.
