-- meli_silver.regiones y meli_silver.q_regiones
-- Prioridad (una fila, un motivo): cast_fallido, nulo_obligatorio, duplicado, fk_huerfana, fecha_incoherente.
-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_silver.regiones`
OPTIONS (
  description="Silver regiones. Lab de portafolio. Marca con fines ilustrativos. Tipado, deduplicado, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.regiones`
),
raw AS (
  SELECT
    src.region AS raw_region,
    src.region_nombre AS raw_region_nombre,
    src.zona AS raw_zona,
    NULLIF(UPPER(TRIM(src.region)), '') AS region,
    NULLIF(TRIM(src.region_nombre), '') AS region_nombre,
    NULLIF(LOWER(TRIM(src.zona)), '') AS zona
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN FALSE THEN 'cast_fallido'
      WHEN region IS NULL OR region_nombre IS NULL OR zona IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN FALSE THEN ''
      WHEN region IS NULL THEN 'region vacío'
      WHEN region_nombre IS NULL THEN 'region_nombre vacío'
      WHEN zona IS NULL THEN 'zona vacío'
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
        PARTITION BY IF(motivo_base IS NULL, region, CAST(NULL AS STRING))
        ORDER BY region_nombre, zona
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
      
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por region'
      
      ELSE NULL
    END AS regla
  FROM ranked
  
)
SELECT
  region,
  region_nombre,
  zona
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY region
  ORDER BY region_nombre, zona
) = 1;

CREATE OR REPLACE TABLE `meli_silver.q_regiones`
OPTIONS (
  description="Cuarentena de regiones. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.regiones`
),
raw AS (
  SELECT
    src.region AS raw_region,
    src.region_nombre AS raw_region_nombre,
    src.zona AS raw_zona,
    NULLIF(UPPER(TRIM(src.region)), '') AS region,
    NULLIF(TRIM(src.region_nombre), '') AS region_nombre,
    NULLIF(LOWER(TRIM(src.zona)), '') AS zona
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN FALSE THEN 'cast_fallido'
      WHEN region IS NULL OR region_nombre IS NULL OR zona IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN FALSE THEN ''
      WHEN region IS NULL THEN 'region vacío'
      WHEN region_nombre IS NULL THEN 'region_nombre vacío'
      WHEN zona IS NULL THEN 'zona vacío'
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
        PARTITION BY IF(motivo_base IS NULL, region, CAST(NULL AS STRING))
        ORDER BY region_nombre, zona
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
      
      ELSE NULL
    END AS motivo,
    CASE
      WHEN ranked.motivo_base IS NOT NULL THEN ranked.regla_base
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por region'
      
      ELSE NULL
    END AS regla
  FROM ranked
  
)
SELECT
  raw_region AS region,
  raw_region_nombre AS region_nombre,
  raw_zona AS zona,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
