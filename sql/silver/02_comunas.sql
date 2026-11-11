-- meli_silver.comunas y meli_silver.q_comunas
-- Prioridad (una fila, un motivo): cast_fallido, nulo_obligatorio, duplicado, fk_huerfana, fecha_incoherente.
-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_silver.comunas`
OPTIONS (
  description="Silver comunas. Lab de portafolio. Marca con fines ilustrativos. Tipado, deduplicado, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.comunas`
),
raw AS (
  SELECT
    src.comuna_id AS raw_comuna_id,
    src.comuna_nombre AS raw_comuna_nombre,
    src.region AS raw_region,
    NULLIF(TRIM(src.comuna_id), '') AS comuna_id,
    NULLIF(TRIM(src.comuna_nombre), '') AS comuna_nombre,
    NULLIF(UPPER(TRIM(src.region)), '') AS region
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN FALSE THEN 'cast_fallido'
      WHEN comuna_id IS NULL OR comuna_nombre IS NULL OR region IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN FALSE THEN ''
      WHEN comuna_id IS NULL THEN 'comuna_id vacío'
      WHEN comuna_nombre IS NULL THEN 'comuna_nombre vacío'
      WHEN region IS NULL THEN 'region vacío'
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
        PARTITION BY IF(motivo_base IS NULL, comuna_id, CAST(NULL AS STRING))
        ORDER BY comuna_nombre, region
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
      WHEN ranked.region IS NOT NULL AND fk_regiones_region.region IS NULL THEN 'fk_huerfana'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por comuna_id'
      WHEN ranked.region IS NOT NULL AND fk_regiones_region.region IS NULL THEN 'region no está en silver.regiones'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.regiones` AS fk_regiones_region
    ON ranked.region = fk_regiones_region.region
)
SELECT
  comuna_id,
  comuna_nombre,
  region
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY comuna_id
  ORDER BY comuna_nombre, region
) = 1;

CREATE OR REPLACE TABLE `meli_silver.q_comunas`
OPTIONS (
  description="Cuarentena de comunas. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.comunas`
),
raw AS (
  SELECT
    src.comuna_id AS raw_comuna_id,
    src.comuna_nombre AS raw_comuna_nombre,
    src.region AS raw_region,
    NULLIF(TRIM(src.comuna_id), '') AS comuna_id,
    NULLIF(TRIM(src.comuna_nombre), '') AS comuna_nombre,
    NULLIF(UPPER(TRIM(src.region)), '') AS region
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN FALSE THEN 'cast_fallido'
      WHEN comuna_id IS NULL OR comuna_nombre IS NULL OR region IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN FALSE THEN ''
      WHEN comuna_id IS NULL THEN 'comuna_id vacío'
      WHEN comuna_nombre IS NULL THEN 'comuna_nombre vacío'
      WHEN region IS NULL THEN 'region vacío'
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
        PARTITION BY IF(motivo_base IS NULL, comuna_id, CAST(NULL AS STRING))
        ORDER BY comuna_nombre, region
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
      WHEN ranked.region IS NOT NULL AND fk_regiones_region.region IS NULL THEN 'fk_huerfana'
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por comuna_id'
      WHEN ranked.region IS NOT NULL AND fk_regiones_region.region IS NULL THEN 'region no está en silver.regiones'
      ELSE NULL
    END AS regla
  FROM ranked
  LEFT JOIN `meli_silver.regiones` AS fk_regiones_region
    ON ranked.region = fk_regiones_region.region
)
SELECT
  raw_comuna_id AS comuna_id,
  raw_comuna_nombre AS comuna_nombre,
  raw_region AS region,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
