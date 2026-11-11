# Paso 3 — Silver tipado y cuarentena

> **Lab de portafolio. Marca con fines ilustrativos.**

**Dataset:** `meli_silver` · **location:** `US` · **expiración:** 60 días.  
**Entrada:** `meli_bronze`, todo NULLABLE.  
**Salida:** una tabla silver por entidad y `q_<tabla>` con la fila cruda, un motivo y la regla.

El bronze **cambió** respecto de la corrida que ya dio `RESULTADO: OK` en la Mac. Se agregaron `cast_fallido` y `entrega_antes_despacho` para poder probar el `SAFE_CAST` y la fecha incoherente en el envío, no solo en el evento. `make run` reconstruye CSV, bronze y silver desde cero.

---

## Qué

Pasar de un landing crudo a un silver con tipo, una fila por llave natural y FK que existen. Ninguna fila de bronze desaparece: o queda en silver o queda en cuarentena.

Archivos: `sql/silver/NN_<tabla>.sql` (el SQL que corre BigQuery), `src/silver_rules.py` (el mismo spec, evaluado en pandas), `src/build_silver.py`, `src/verify_silver.py`.

## Por qué

Bronze acepta todo para que el load no rechace nulos. Si el dashboard leyera eso, un `AVG` de porcentajes sería el menor de los problemas: un envío con `fecha_promesa = NO-CAST` o con la entrega antes del despacho entraría al numerador. Silver es el contrato. La cuarentena es la evidencia de lo que se sacó y por qué, con un conteo que cierra: `bronze = silver + cuarentena`.

En el sandbox no hay `MERGE` ni `UPDATE`. La transformación es `CREATE OR REPLACE TABLE … AS SELECT`. A los 60 días el sandbox borra las tablas. No hay estado que migrar: `make run` vuelve a crearlas.

## Cómo

Orden de build, porque la FK se valida contra la dimensión **silver** (no contra bronze: un padre en cuarentena no alcanza para dar por buena a la hija):

1. `regiones`
2. `comunas`
3. `centros_fulfillment`
4. `carriers`
5. `sellers`
6. `ordenes`
7. `envios`
8. `eventos_tracking`

Cada archivo hace dos `CREATE OR REPLACE`: la tabla limpia y `q_<tabla>`.

En cada fila:

- `TRIM`. Códigos de estado, tipo y motivo en minúsculas. Región en mayúsculas. `activo` en minúsculas y luego `SAFE_CAST` a `BOOL`. Fechas a `DATE`, timestamps a `TIMESTAMP`.
- El contrato no tiene medidas `INT64` ni `NUMERIC`. No se inventaron columnas para poder escribir el cast. Los tipos que sí existen se castean de verdad.
- Dedup con `QUALIFY ROW_NUMBER()` sobre la llave natural, solo entre filas que ya pasaron cast y nulos. El duplicado exacto se queda una vez en silver; la copia va a cuarentena.
- FK opcional vacía (`fc_id` en Flex, `carrier_id` antes del handoff) no es huérfana. FK con valor que no está en la dimensión silver, sí.

### Prioridad de motivos

Una fila con varios problemas sale **una vez**, con el primer motivo de esta lista. La `regla` nombra el campo.

| Orden | Motivo | Cuándo |
|---|---|---|
| 1 | `cast_fallido` | Hay texto y `SAFE_CAST` devuelve NULL |
| 2 | `nulo_obligatorio` | Falta la PK o un campo requerido |
| 3 | `duplicado` | `ROW_NUMBER > 1` de la llave, entre las que pasaron 1 y 2 |
| 4 | `fk_huerfana` | El valor no está en la dimensión silver |
| 5 | `fecha_incoherente` | `ts_entrega < ts_despacho`, o un evento `entregado` anterior al despacho del envío |

El cast va primero: si `activo = NO-CAST` y además la PK viene vacía, el motivo es `cast_fallido`. No se promedia ni se parte la fila en dos cuarentenas. Si no, `bronze = silver + cuarentena` no cerraría.

El duplicado se evalúa antes que la FK. La copia de una fila válida es `duplicado`. La copia de una fila rota ni siquiera entra al `ROW_NUMBER`: ya salió por cast o por nulo.

### Conteos esperados (seed 42)

Silver = núcleo limpio. Cuarentena = filas extra. La suma es el bronze.

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

Motivos (solo los distintos de cero):

| Tabla | cast_fallido | nulo_obligatorio | duplicado | fk_huerfana | fecha_incoherente |
|---|---:|---:|---:|---:|---:|
| `regiones` | 0 | 1 | 1 | 0 | 0 |
| `comunas` | 0 | 1 | 1 | 2 | 0 |
| `centros_fulfillment` | 2 | 1 | 1 | 1 | 0 |
| `carriers` | 2 | 1 | 1 | 0 | 0 |
| `sellers` | 2 | 1 | 2 | 2 | 0 |
| `ordenes` | 4 | 14 | 10 | 12 | 0 |
| `envios` | 6 | 18 | 12 | 20 | 8 |
| `eventos_tracking` | 6 | 18 | 12 | 15 | 20 |

`nulo_obligatorio` junta clave vacía y fecha requerida vacía. `fecha_incoherente` de envíos son las 8 filas nuevas; la de eventos son los 20 `entregado` puestos 3 horas antes del despacho. En silver ese conteo de huérfanas es 0.

`verify_silver` imprime las dos tablas y `RESULTADO: OK` o `RESULTADO: FALLA`.

### Correrlo

```bash
cd /Users/julio/meli-fulfillment-bq
source .venv/bin/activate
git fetch origin
git checkout cursor/paso-03-silver-1363
pip install -r requirements.txt
export GCP_PROJECT=meli-fulfillment-jp
make run
```

`make run` = `make data` + bronze + silver + `verify_bronze` + `verify_silver`. Sin GCP, `make run DRY=1` clasifica los CSV con pandas y no llama a BigQuery.

## Cómo se verificó

No hay credenciales GCP en el entorno del agente. No se ejecutó el `CREATE OR REPLACE` contra `meli-fulfillment-jp`.

- `make test` → **29 passed**. Incluye el SQL renderizado (SAFE_CAST, TRIM, QUALIFY, sin DML), la prioridad en un caso chico (el cast gana al nulo; el `TRIM` de `rm` encuentra la región) y la reconciliación del CSV completo contra el manifest.
- `make run DRY=1` → bronze `RESULTADO: OK` y silver `RESULTADO: OK`, con `huerfanas_en_silver 0`.

## Cómo defenderlo en una entrevista

- **¿Por qué no borrar las filas malas?** Porque el número de envíos del dashboard tiene que poder explicarse. Si silver tiene 32.000 y bronze 32.064, las 64 están en `q_envios` con motivo. Eso es reconciliación, no un filtro silencioso.
- **¿Por qué un solo motivo?** Una fila con cast roto y FK rota no son dos problemas independientes para el conteo. Si la cuento dos veces, `silver + cuarentena` se pasa de bronze. La prioridad está escrita y es la misma en el SQL y en pandas.
- **¿Por qué la FK contra silver y no contra bronze?** El padre también puede estar en cuarentena. Un envío que apunta a un seller cuya fila no sobrevivió no tiene dimensión.
- **¿Por qué `CREATE OR REPLACE` y no `MERGE`?** El sandbox no tiene DML. Además las tablas mueren a los 60 días. Reconstruir es el diseño, no un accidente.
- **¿El porcentaje de atrasos usa la cuarentena?** No. El KPI sigue siendo `SUM(atrasado) / SUM(entregados)` sobre silver. La cuarentena no entra al denominador ni al numerador. Meterla “para no perder filas” en el porcentaje volvería a mezclar poblaciones.
- **¿Qué no casteamos a INT64 o NUMERIC?** El contrato de este lab no trae montos ni cantidades. Inventar una columna para mostrar el cast sería un contrato falso.
