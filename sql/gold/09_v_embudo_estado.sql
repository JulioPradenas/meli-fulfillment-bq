-- Embudo de hitos (anidado) y, en la misma vista, no se mezcla con el estado final.
-- Cada hito es un conteo aditivo. No es un porcentaje.
-- creado: todos los envíos. despachado: tiene ts_despacho. entregado / a_tiempo: flags.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE VIEW `meli_gold.v_embudo_hitos`
OPTIONS (
  description="Hitos del envío con n_envios aditivo. Lab de portafolio. Marca con fines ilustrativos.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT 'creado' AS hito, 1 AS orden_hito, COUNT(*) AS n_envios
FROM `meli_gold.f_envios`
UNION ALL
SELECT 'despachado', 2, COUNTIF(ts_despacho IS NOT NULL)
FROM `meli_gold.f_envios`
UNION ALL
SELECT 'entregado', 3, SUM(es_entregado)
FROM `meli_gold.f_envios`
UNION ALL
SELECT 'a_tiempo', 4, SUM(es_a_tiempo)
FROM `meli_gold.f_envios`
UNION ALL
SELECT 'cancelado_logistica', 5, SUM(es_cancelado_logistica)
FROM `meli_gold.f_envios`;

CREATE OR REPLACE VIEW `meli_gold.v_embudo_estado`
OPTIONS (
  description="Estado final del envío. Una fila por estado, n_envios aditivo. Lab de portafolio. Marca con fines ilustrativos.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  estado,
  COUNT(*) AS n_envios
FROM `meli_gold.f_envios`
GROUP BY estado;
