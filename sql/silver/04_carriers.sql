-- meli_silver.carriers y meli_silver.q_carriers
-- Prioridad (una fila, un motivo): cast_fallido, nulo_obligatorio, duplicado, fk_huerfana, fecha_incoherente.
-- SAFE_CAST, TRIM, QUALIFY vía ROW_NUMBER, FK contra las dims silver.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_silver.carriers`
OPTIONS (
  description="Silver carriers. Lab de portafolio. Marca con fines ilustrativos. Tipado, deduplicado, FK contra silver. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.carriers`
),
raw AS (
  SELECT
    src.carrier_id AS raw_carrier_id,
    src.carrier_nombre AS raw_carrier_nombre,
    src.tipo_servicio AS raw_tipo_servicio,
    src.activo AS raw_activo,
    NULLIF(TRIM(src.carrier_id), '') AS carrier_id,
    NULLIF(TRIM(src.carrier_nombre), '') AS carrier_nombre,
    NULLIF(LOWER(TRIM(src.tipo_servicio)), '') AS tipo_servicio,
    NULLIF(LOWER(TRIM(src.activo)), '') AS activo_txt,
    SAFE_CAST(NULLIF(LOWER(TRIM(src.activo)), '') AS BOOL) AS activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'cast_fallido'
      WHEN carrier_id IS NULL OR carrier_nombre IS NULL OR tipo_servicio IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'SAFE_CAST falló en activo'
      WHEN carrier_id IS NULL THEN 'carrier_id vacío'
      WHEN carrier_nombre IS NULL THEN 'carrier_nombre vacío'
      WHEN tipo_servicio IS NULL THEN 'tipo_servicio vacío'
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
        PARTITION BY IF(motivo_base IS NULL, carrier_id, CAST(NULL AS STRING))
        ORDER BY carrier_nombre, tipo_servicio, activo
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
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por carrier_id'
      
      ELSE NULL
    END AS regla
  FROM ranked
  
)
SELECT
  carrier_id,
  carrier_nombre,
  tipo_servicio,
  activo
FROM resolved
WHERE motivo IS NULL
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY carrier_id
  ORDER BY carrier_nombre, tipo_servicio, activo
) = 1;

CREATE OR REPLACE TABLE `meli_silver.q_carriers`
OPTIONS (
  description="Cuarentena de carriers. Lab de portafolio. Marca con fines ilustrativos. Una fila, un motivo, el de mayor prioridad. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
WITH src AS (
  SELECT * FROM `meli_bronze.carriers`
),
raw AS (
  SELECT
    src.carrier_id AS raw_carrier_id,
    src.carrier_nombre AS raw_carrier_nombre,
    src.tipo_servicio AS raw_tipo_servicio,
    src.activo AS raw_activo,
    NULLIF(TRIM(src.carrier_id), '') AS carrier_id,
    NULLIF(TRIM(src.carrier_nombre), '') AS carrier_nombre,
    NULLIF(LOWER(TRIM(src.tipo_servicio)), '') AS tipo_servicio,
    NULLIF(LOWER(TRIM(src.activo)), '') AS activo_txt,
    SAFE_CAST(NULLIF(LOWER(TRIM(src.activo)), '') AS BOOL) AS activo
  FROM src
),
flagged AS (
  SELECT
    *,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'cast_fallido'
      WHEN carrier_id IS NULL OR carrier_nombre IS NULL OR tipo_servicio IS NULL OR activo IS NULL THEN 'nulo_obligatorio'
      ELSE NULL
    END AS motivo_base,
    CASE
      WHEN (activo_txt IS NOT NULL AND activo IS NULL) THEN 'SAFE_CAST falló en activo'
      WHEN carrier_id IS NULL THEN 'carrier_id vacío'
      WHEN carrier_nombre IS NULL THEN 'carrier_nombre vacío'
      WHEN tipo_servicio IS NULL THEN 'tipo_servicio vacío'
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
        PARTITION BY IF(motivo_base IS NULL, carrier_id, CAST(NULL AS STRING))
        ORDER BY carrier_nombre, tipo_servicio, activo
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
      WHEN ranked.rn > 1 THEN 'ROW_NUMBER > 1 por carrier_id'
      
      ELSE NULL
    END AS regla
  FROM ranked
  
)
SELECT
  raw_carrier_id AS carrier_id,
  raw_carrier_nombre AS carrier_nombre,
  raw_tipo_servicio AS tipo_servicio,
  raw_activo AS activo,
  motivo,
  regla
FROM resolved
WHERE motivo IS NOT NULL;
