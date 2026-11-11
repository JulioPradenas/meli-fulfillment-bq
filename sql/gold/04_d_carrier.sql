-- d_carrier. Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_gold.d_carrier`
OPTIONS (
  description="Carriers. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  carrier_id,
  carrier_nombre,
  tipo_servicio,
  activo
FROM `meli_silver.carriers`;
