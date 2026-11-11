-- meli_silver.ordenes y meli_silver.q_ordenes
-- Prioridad (una fila, un motivo): cast_fallido, nulo_obligatorio, duplicado, fk_huerfana, fecha_incoherente.
-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_silver.ordenes`
OPTIONS (
  description="Silver ordenes. Lab de portafolio. Marca con fines ilustrativos. Tipado, deduplicado, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.ordenes`
),
raw AS (
  SELECT
    src.orden_id AS raw_orden_id,
    src.seller_id AS raw_seller_id,
    src.ts_creacion AS raw_ts_creacion,
    src.comuna_destino_id AS raw_comuna_destino_id,
    src.estado_orden AS raw_estado_orden,
    NULLIF(TRIM(CAST(src.orden_id AS STRING)), '') AS orden_id,
    NULLIF(TRIM(CAST(src.seller_id AS STRING)), '') AS seller_id,
    NULLIF(TRIM(CAST(src.ts_creacion AS STRING)), '') AS ts_creacion_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_creacion AS STRING)), '') AS TIMESTAMP) AS ts_creacion,
    NULLIF(TRIM(CAST(src.comuna_destino_id AS STRING)), '') AS comuna_destino_id,
    NULLIF(LOWER(TRIM(CAST(src.estado_orden AS STRING))), '') AS estado_orden
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (ts_creacion_txt IS NOT NULL AND ts_creacion IS NULL) THEN 'cast_fallido'
      WHEN orden_id IS NULL OR seller_id IS NULL OR ts_creacion IS NULL OR comuna_destino_id IS NULL OR estado_orden IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (ts_creacion_txt IS NOT NULL AND ts_creacion IS NULL) THEN 'SAFE_CAST falló en ts_creacion'
      WHEN orden_id IS NULL THEN 'orden_id vacío'
      WHEN seller_id IS NULL THEN 'seller_id vacío'
      WHEN ts_creacion IS NULL THEN 'ts_creacion vacío'
      WHEN comuna_destino_id IS NULL THEN 'comuna_destino_id vacío'
      WHEN estado_orden IS NULL THEN 'estado_orden vacío'
      ELSE NULL
    END AS regla_base
  FROM raw
),
ranked AS (
  SELECT
    *,
    IF(
      motivo_base IS NULL,
      ROW_NUMBER() OVER (
        PARTITION BY IF(motivo_base IS NULL, orden_id, CAST(NULL AS STRING))
        ORDER BY seller_id, ts_creacion, comuna_destino_id, estado_orden
      ),
      NULL
    ) AS rn
  FROM flagged
),
resolved AS (
  SELECT
    ranked.*,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.motivo_base
      WHEN ranked.rn > 1 THEN 'duplicado'
      WHEN ranked.seller_id IS NOT NULL AND fk_sellers_seller_id.seller_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.comuna_destino_id IS NOT NULL AND fk_comunas_comuna_destino_id.comuna_id IS NULL THEN 'fk_huerfana'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por orden_id'
      WHEN ranked.seller_id IS NOT NULL AND fk_sellers_seller_id.seller_id IS NULL THEN 'seller_id no está en silver.sellers'
      WHEN ranked.comuna_destino_id IS NOT NULL AND fk_comunas_comuna_destino_id.comuna_id IS NULL THEN 'comuna_destino_id no está en silver.comunas'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.sellers` AS fk_sellers_seller_id
    ON ranked.seller_id = fk_sellers_seller_id.seller_id
  LEFT JOIN `meli_silver.comunas` AS fk_comunas_comuna_destino_id
    ON ranked.comuna_destino_id = fk_comunas_comuna_destino_id.comuna_id
)
SELECT
  orden_id,
  seller_id,
  ts_creacion,
  comuna_destino_id,
  estado_orden
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY orden_id
  ORDER BY seller_id, ts_creacion, comuna_destino_id, estado_orden
) = 1;

CREATE OR REPLACE TABLE `meli_silver.q_ordenes`
OPTIONS (
  description="Cuarentena de ordenes. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.ordenes`
),
raw AS (
  SELECT
    src.orden_id AS raw_orden_id,
    src.seller_id AS raw_seller_id,
    src.ts_creacion AS raw_ts_creacion,
    src.comuna_destino_id AS raw_comuna_destino_id,
    src.estado_orden AS raw_estado_orden,
    NULLIF(TRIM(CAST(src.orden_id AS STRING)), '') AS orden_id,
    NULLIF(TRIM(CAST(src.seller_id AS STRING)), '') AS seller_id,
    NULLIF(TRIM(CAST(src.ts_creacion AS STRING)), '') AS ts_creacion_txt,
    SAFE_CAST(NULLIF(TRIM(CAST(src.ts_creacion AS STRING)), '') AS TIMESTAMP) AS ts_creacion,
    NULLIF(TRIM(CAST(src.comuna_destino_id AS STRING)), '') AS comuna_destino_id,
    NULLIF(LOWER(TRIM(CAST(src.estado_orden AS STRING))), '') AS estado_orden
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (ts_creacion_txt IS NOT NULL AND ts_creacion IS NULL) THEN 'cast_fallido'
      WHEN orden_id IS NULL OR seller_id IS NULL OR ts_creacion IS NULL OR comuna_destino_id IS NULL OR estado_orden IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (ts_creacion_txt IS NOT NULL AND ts_creacion IS NULL) THEN 'SAFE_CAST falló en ts_creacion'
      WHEN orden_id IS NULL THEN 'orden_id vacío'
      WHEN seller_id IS NULL THEN 'seller_id vacío'
      WHEN ts_creacion IS NULL THEN 'ts_creacion vacío'
      WHEN comuna_destino_id IS NULL THEN 'comuna_destino_id vacío'
      WHEN estado_orden IS NULL THEN 'estado_orden vacío'
      ELSE NULL
    END AS regla_base
  FROM raw
),
ranked AS (
  SELECT
    *,
    IF(
      motivo_base IS NULL,
      ROW_NUMBER() OVER (
        PARTITION BY IF(motivo_base IS NULL, orden_id, CAST(NULL AS STRING))
        ORDER BY seller_id, ts_creacion, comuna_destino_id, estado_orden
      ),
      NULL
    ) AS rn
  FROM flagged
),
resolved AS (
  SELECT
    ranked.*,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.motivo_base
      WHEN ranked.rn > 1 THEN 'duplicado'
      WHEN ranked.seller_id IS NOT NULL AND fk_sellers_seller_id.seller_id IS NULL THEN 'fk_huerfana'
      WHEN ranked.comuna_destino_id IS NOT NULL AND fk_comunas_comuna_destino_id.comuna_id IS NULL THEN 'fk_huerfana'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por orden_id'
      WHEN ranked.seller_id IS NOT NULL AND fk_sellers_seller_id.seller_id IS NULL THEN 'seller_id no está en silver.sellers'
      WHEN ranked.comuna_destino_id IS NOT NULL AND fk_comunas_comuna_destino_id.comuna_id IS NULL THEN 'comuna_destino_id no está en silver.comunas'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.sellers` AS fk_sellers_seller_id
    ON ranked.seller_id = fk_sellers_seller_id.seller_id
  LEFT JOIN `meli_silver.comunas` AS fk_comunas_comuna_destino_id
    ON ranked.comuna_destino_id = fk_comunas_comuna_destino_id.comuna_id
)
SELECT
  raw_orden_id AS orden_id,
  raw_seller_id AS seller_id,
  raw_ts_creacion AS ts_creacion,
  raw_comuna_destino_id AS comuna_destino_id,
  raw_estado_orden AS estado_orden,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
