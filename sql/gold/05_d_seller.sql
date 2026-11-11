-- d_seller. Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_gold.d_seller`
OPTIONS (
  description="Sellers. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  seller_id,
  seller_nombre,
  tipo_seller,
  region_origen,
  activo
FROM `meli_silver.sellers`;
