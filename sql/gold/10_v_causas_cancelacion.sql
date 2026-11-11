-- Causas de cancelación logística. n_causa es aditivo.
-- Looker: SUM(n_causa) del motivo / SUM(n_causa) de todos los motivos del filtro.
-- No se repite el total en cada fila: SUM de un total repetido inflaría el denominador.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE VIEW `meli_gold.v_causas_cancelacion`
OPTIONS (
  description="Cancelaciones logísticas por motivo, región y centro. n_causa aditivo. Lab de portafolio. Marca con fines ilustrativos.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  motivo_cancelacion_logistica AS motivo,
  region_id,
  fc_id,
  COUNT(*) AS n_causa
FROM `meli_gold.f_envios`
WHERE es_cancelado_logistica = 1
GROUP BY motivo_cancelacion_logistica, region_id, fc_id;
