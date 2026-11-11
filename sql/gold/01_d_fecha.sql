-- d_fecha: un día por fila, horizonte del lab más la cola de entregas tardías.
-- Semana ISO empieza el lunes (DATE_TRUNC ISOWEEK). Sin partición.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_gold.d_fecha`
OPTIONS (
  description="Calendario gold. Semana ISO desde el lunes. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  fecha,
  EXTRACT(YEAR FROM fecha) AS anio,
  EXTRACT(MONTH FROM fecha) AS mes,
  EXTRACT(ISOWEEK FROM fecha) AS semana_iso,
  EXTRACT(ISOYEAR FROM fecha) AS anio_iso,
  DATE_TRUNC(fecha, ISOWEEK) AS lunes_semana,
  IF(EXTRACT(DAYOFWEEK FROM fecha) IN (1, 7), 1, 0) AS es_fin_de_semana
FROM UNNEST(GENERATE_DATE_ARRAY(DATE '2026-05-01', DATE '2026-11-30')) AS fecha;
