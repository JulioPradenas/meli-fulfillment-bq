-- d_geografia: comuna + región + grupo para el dashboard.
-- grupo_zona sale de los datos: RM aparte, extremos = AP/AN/AI/MA,
-- centro = zona centro sin RM (VS, LI, ML), el resto conserva norte o sur.
-- Lab de portafolio. Marca con fines ilustrativos.

CREATE OR REPLACE TABLE `meli_gold.d_geografia`
OPTIONS (
  description="Comuna con su región y grupo_zona. Lab de portafolio. Marca con fines ilustrativos. Expira a los 60 días.",
  expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 60 DAY)
)
AS
SELECT
  c.comuna_id,
  c.comuna_nombre,
  c.region AS region_id,
  r.region_nombre,
  r.zona,
  CASE
    WHEN c.region = 'RM' THEN 'RM'
    WHEN c.region IN ('AP', 'AN', 'AI', 'MA') THEN 'extremos'
    WHEN r.zona = 'centro' THEN 'centro'
    ELSE r.zona
  END AS grupo_zona,
  IF(c.region IN ('AP', 'AN', 'AI', 'MA'), 1, 0) AS es_extremo,
  IF(c.region = 'RM', 1, 0) AS es_rm
FROM `meli_silver.comunas` AS c
INNER JOIN `meli_silver.regiones` AS r
  ON c.region = r.region;
