-- meli_silver.sellers y meli_silver.q_sellers
-- Prioridad (una fila, un motivo): cast_fallido, nulo_obligatorio, duplicado, fk_huerfana, fecha_incoherente.
-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_silver.sellers`
OPTIONS (
  description="Silver sellers. Lab de portafolio. Marca con fines ilustrativos. Tipado, deduplicado, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.sellers`
),
raw AS (
  SELECT
    src.seller_id AS raw_seller_id,
    src.seller_nombre AS raw_seller_nombre,
    src.tipo_seller AS raw_tipo_seller,
    src.region_origen AS raw_region_origen,
    src.activo AS raw_activo,
    NULLIF(TRIM(CAST(src.seller_id AS STRING)), '') AS seller_id,
    NULLIF(TRIM(CAST(src.seller_nombre AS STRING)), '') AS seller_nombre,
    NULLIF(LOWER(TRIM(CAST(src.tipo_seller AS STRING))), '') AS tipo_seller,
    NULLIF(UPPER(TRIM(CAST(src.region_origen AS STRING))), '') AS region_origen,
    NULLIF(LOWER(TRIM(CAST(src.activo AS STRING))), '') AS activo_txt,
    SAFE_CAST(CASE LOWER(TRIM(CAST(src.activo AS STRING)))
      WHEN '1' THEN 'true'
      WHEN '0' THEN 'false'
      ELSE NULLIF(LOWER(TRIM(CAST(src.activo AS STRING))), '')
    END AS BOOL) AS activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'cast_fallido'
      WHEN seller_id IS NULL OR seller_nombre IS NULL OR tipo_seller IS NULL OR region_origen IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'SAFE_CAST falló en activo'
      WHEN seller_id IS NULL THEN 'seller_id vacío'
      WHEN seller_nombre IS NULL THEN 'seller_nombre vacío'
      WHEN tipo_seller IS NULL THEN 'tipo_seller vacío'
      WHEN region_origen IS NULL THEN 'region_origen vacío'
      WHEN activo IS NULL THEN 'activo vacío'
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
        PARTITION BY IF(motivo_base IS NULL, seller_id, CAST(NULL AS STRING))
        ORDER BY seller_nombre, tipo_seller, region_origen, activo
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
      WHEN ranked.region_origen IS NOT NULL AND fk_regiones_region_origen.region IS NULL THEN 'fk_huerfana'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por seller_id'
      WHEN ranked.region_origen IS NOT NULL AND fk_regiones_region_origen.region IS NULL THEN 'region_origen no está en silver.regiones'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.regiones` AS fk_regiones_region_origen
    ON ranked.region_origen = fk_regiones_region_origen.region
)
SELECT
  seller_id,
  seller_nombre,
  tipo_seller,
  region_origen,
  activo
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY seller_id
  ORDER BY seller_nombre, tipo_seller, region_origen, activo
) = 1;

CREATE OR REPLACE TABLE `meli_silver.q_sellers`
OPTIONS (
  description="Cuarentena de sellers. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.sellers`
),
raw AS (
  SELECT
    src.seller_id AS raw_seller_id,
    src.seller_nombre AS raw_seller_nombre,
    src.tipo_seller AS raw_tipo_seller,
    src.region_origen AS raw_region_origen,
    src.activo AS raw_activo,
    NULLIF(TRIM(CAST(src.seller_id AS STRING)), '') AS seller_id,
    NULLIF(TRIM(CAST(src.seller_nombre AS STRING)), '') AS seller_nombre,
    NULLIF(LOWER(TRIM(CAST(src.tipo_seller AS STRING))), '') AS tipo_seller,
    NULLIF(UPPER(TRIM(CAST(src.region_origen AS STRING))), '') AS region_origen,
    NULLIF(LOWER(TRIM(CAST(src.activo AS STRING))), '') AS activo_txt,
    SAFE_CAST(CASE LOWER(TRIM(CAST(src.activo AS STRING)))
      WHEN '1' THEN 'true'
      WHEN '0' THEN 'false'
      ELSE NULLIF(LOWER(TRIM(CAST(src.activo AS STRING))), '')
    END AS BOOL) AS activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'cast_fallido'
      WHEN seller_id IS NULL OR seller_nombre IS NULL OR tipo_seller IS NULL OR region_origen IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'SAFE_CAST falló en activo'
      WHEN seller_id IS NULL THEN 'seller_id vacío'
      WHEN seller_nombre IS NULL THEN 'seller_nombre vacío'
      WHEN tipo_seller IS NULL THEN 'tipo_seller vacío'
      WHEN region_origen IS NULL THEN 'region_origen vacío'
      WHEN activo IS NULL THEN 'activo vacío'
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
        PARTITION BY IF(motivo_base IS NULL, seller_id, CAST(NULL AS STRING))
        ORDER BY seller_nombre, tipo_seller, region_origen, activo
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
      WHEN ranked.region_origen IS NOT NULL AND fk_regiones_region_origen.region IS NULL THEN 'fk_huerfana'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por seller_id'
      WHEN ranked.region_origen IS NOT NULL AND fk_regiones_region_origen.region IS NULL THEN 'region_origen no está en silver.regiones'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.regiones` AS fk_regiones_region_origen
    ON ranked.region_origen = fk_regiones_region_origen.region
)
SELECT
  raw_seller_id AS seller_id,
  raw_seller_nombre AS seller_nombre,
  raw_tipo_seller AS tipo_seller,
  raw_region_origen AS region_origen,
  raw_activo AS activo,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
