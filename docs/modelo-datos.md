# Modelo de datos — Meli Fulfillment

> **Lab de portafolio. Marca con fines ilustrativos.**  
> Marketplace de fulfillment al estilo Mercado Libre, en Chile. Sin logos y sin datos reales de la marca.

**Analista:** Julio Pradenas  
**Repo:** `meli-fulfillment-bq`  
**Paso:** 1 — forma de los datos, antes del generador, de BigQuery y de GCP.

Este documento es el contrato de grano y de métricas. El Paso 2 baja cada columna a un CSV. El Paso 7 materializa la estrella. Si una fórmula cambia, se cambia aquí primero.

---

## 1. Objetivo

Responder, con un solo número por KPI, si el fulfillment cumple la **fecha promesa** de cada envío, por qué se cancela cuando la causa es logística, y cuánto tarda en llegar.

El grano de la decisión es el **envío**, no la orden ni el evento de tracking. Una orden de varios sellers (o un split de centros) produce varios envíos; cada uno tiene su propia promesa.

---

## 2. Preguntas que el modelo tiene que poder contestar

1. De los envíos entregados, ¿qué porcentaje llegó **después** de `fecha_promesa`?
2. ¿Cuál es el cumplimiento de promesa (entregados a tiempo / entregados) del período y de la semana?
3. ¿Qué causas explican las cancelaciones logísticas, y en qué seller o centro se concentran?
4. ¿Cuál es el lead time real (creación → entrega) y qué tramo se lo queda: preparación o tránsito?
5. ¿El incumplimiento de un seller se explica por el centro que lo opera o por la comuna de destino?

Cada página del dashboard futuro (sección 10) se queda con un subconjunto de estas preguntas. Ninguna página lee bronze.

---

## 3. Convenciones

| Regla | Definición |
|---|---|
| Zona horaria | `America/Santiago`. La fecha de un hecho es el día civil en Santiago, no el día UTC. |
| Promesa | `fecha_promesa` es un **DATE**. Entregar el mismo día prometido es a tiempo. El intradiario no entra al KPI de promesa. |
| Lead time | Se mide en **horas** entre timestamps. No es un porcentaje. |
| Porcentajes | `SUM` del numerador / `SUM` del denominador, los dos al grano que se está mirando. |
| Promedio de porcentajes | Prohibido. Un 10% sobre 20 envíos no pesa lo mismo que un 10% sobre 2.000. |
| Promedio de promedios | Prohibido para el lead time ya agregado (por región, por FC, por semana). |
| PII | No hay RUT, nombre, mail, teléfono ni dirección. El destino baja hasta comuna y región. |
| Idioma de códigos | snake_case sin tildes (`cancelado_logistica`). El nombre visible vive en la dimensión. |

**Regla: los porcentajes se calculan como SUM/SUM, nunca como promedio de porcentajes.**

En el grano de `f_envios` (una fila, un envío, el mismo peso), `AVG(lead_time_horas)` coincide con `SUM(lead_time_horas) / SUM(entregados)`. Esa igualdad se rompe si la fila ya es un agregado. El dashboard, agregado o no, usa la forma SUM/SUM.

---

## 4. Tablas fuente

Son el futuro bronze. Aquí se fija **qué es una fila** y **cuál es la clave**. No son CSV todavía.

Una orden tiene N envíos. Un envío tiene N eventos de tracking. El hecho gold no explota los eventos: los pliega a hitos y a indicadores.

### 4.1 `ordenes`

| | |
|---|---|
| Grano | 1 fila = 1 orden (cabecera, no línea) |
| Clave | `orden_id` (PK) |
| FKs | `seller_id` → sellers; `comuna_destino_id` → comunas |

Columnas que importan: `orden_id`, `seller_id`, `ts_creacion`, `comuna_destino_id`, `estado_orden` (`creada`, `pagada`, `cancelada_comprador`, `cerrada`).

Las líneas de la orden (SKU, cantidad, precio) quedan fuera del MVP. El KPI de promesa no se parte por ítem.

### 4.2 `envios`

| | |
|---|---|
| Grano | 1 fila = 1 envío, en su estado **actual** |
| Clave | `envio_id` (PK) |
| FKs | `orden_id` → ordenes; `seller_id` → sellers; `fc_id` → centros de fulfillment (nulo si Flex, sin centro); `carrier_id` → carriers (nulo si aún no hay handoff); `comuna_destino_id` → comunas |

Columnas que importan:

| Columna | Tipo | Nota |
|---|---|---|
| `envio_id` | STRING | PK |
| `orden_id` | STRING | Una orden, varios envíos |
| `seller_id` | STRING | |
| `fc_id` | STRING, nulo | Nulo en Flex |
| `carrier_id` | STRING, nulo | Nulo antes del despacho |
| `comuna_destino_id` | STRING | |
| `tipo_logistica` | STRING | `full`, `flex`, `colecta`, `cross_dock` |
| `ts_creacion` | TIMESTAMP | Alta del envío |
| `ts_despacho` | TIMESTAMP, nulo | Handoff al carrier |
| `ts_entrega` | TIMESTAMP, nulo | Entrega efectiva |
| `fecha_promesa` | DATE | Día prometido, Santiago |
| `estado` | STRING | Ver catálogo en 4.8 |
| `motivo_cancelacion_logistica` | STRING, nulo | Solo si `estado = cancelado_logistica` |

`fecha_entrega_real` no se guarda aquí como columna suelta: es `DATE(ts_entrega, 'America/Santiago')`. En gold sí aparece como columna, porque el usuario del dashboard filtra por ella.

### 4.3 `eventos_tracking`

| | |
|---|---|
| Grano | 1 fila = 1 evento de un envío |
| Clave | `evento_id` (PK). Único también (`envio_id`, `ts_evento`, `codigo_evento`) |
| FKs | `envio_id` → envios |

Columnas: `evento_id`, `envio_id`, `ts_evento`, `codigo_evento`, `fc_id` (nulo), `carrier_id` (nulo), `comuna_id` (nulo).

Códigos de evento: `creado`, `en_preparacion`, `despachado`, `en_transito`, `intento_fallido`, `entregado`, `cancelado_logistica`, `cancelado_no_logistica`, `devuelto`.

Sirve para reconstruir hitos, contar intentos fallidos y, más adelante, auditar. No es el grano del KPI de promesa: un envío entregado tiene varios eventos y no debe contar varias veces.

### 4.4 `sellers`

| | |
|---|---|
| Grano | 1 fila = 1 seller |
| Clave | `seller_id` (PK) |

Columnas: `seller_id`, `seller_nombre`, `tipo_seller` (`pyme`, `marca`, `primera_parte`), `region_origen`, `activo`. Nombres ficticios en el Paso 2.

### 4.5 `centros_fulfillment`

| | |
|---|---|
| Grano | 1 fila = 1 centro de fulfillment (FC) |
| Clave | `fc_id` (PK) |
| FKs | `comuna_id` → comunas |

Columnas: `fc_id`, `fc_nombre`, `tipo_fc` (`mega`, `regional`, `cross_dock`), `comuna_id`, `activo`. El Flex no tiene centro; gold usa la fila centinela `FC_NA` («Sin centro»).

### 4.6 `carriers`

| | |
|---|---|
| Grano | 1 fila = 1 carrier |
| Clave | `carrier_id` (PK) |

Columnas: `carrier_id`, `carrier_nombre`, `tipo_servicio` (`paqueteria`, `same_day`, `moto`), `activo`. Nombres ficticios. Gold usa `CARRIER_NA` («Sin carrier») cuando el envío todavía no se entregó a transporte.

### 4.7 `regiones` y `comunas`

Chile, corte de referencia del lab (16 regiones). La comuna manda: la región de destino del envío es la región de su `comuna_destino_id`.

**`regiones`** — 1 fila = 1 región. PK `region` (código corto).

| `region` | Nombre | Zona |
|---|---|---|
| `AP` | Arica y Parinacota | norte |
| `TA` | Tarapacá | norte |
| `AN` | Antofagasta | norte |
| `AT` | Atacama | norte |
| `CO` | Coquimbo | norte |
| `VS` | Valparaíso | centro |
| `RM` | Metropolitana de Santiago | centro |
| `LI` | O'Higgins | centro |
| `ML` | Maule | centro |
| `NB` | Ñuble | sur |
| `BI` | Biobío | sur |
| `AR` | La Araucanía | sur |
| `LR` | Los Ríos | sur |
| `LL` | Los Lagos | sur |
| `AI` | Aysén | austral |
| `MA` | Magallanes | austral |

**`comunas`** — 1 fila = 1 comuna. PK `comuna_id` (código CUT de 5 dígitos). FK `region`.

Ejemplo de forma, no el padrón completo: `13101` Santiago → `RM`. El Paso 2 carga el conjunto que usen los envíos sintéticos. No hace falta materializar las ~346 comunas si ninguna fila las referencia.

### 4.8 Catálogos cerrados

**`estado` del envío** (uno solo, el actual):

| Código | Cuenta en entregados | Cuenta en cancelación logística |
|---|---|---|
| `creado` | no | no |
| `en_preparacion` | no | no |
| `despachado` | no | no |
| `en_transito` | no | no |
| `entregado` | sí | no |
| `cancelado_logistica` | no | sí |
| `cancelado_no_logistica` | no | no |
| `devuelto` | no | no |

`cancelado_no_logistica` es la anulación del comprador o del pago. No entra al KPI de causas logísticas ni al denominador de atrasos.

**`motivo_cancelacion_logistica`** (obligatorio si el estado es `cancelado_logistica`, nulo en cualquier otro caso):

| Código | Grupo |
|---|---|
| `sin_stock_fc` | centro |
| `capacidad_fc` | centro |
| `dano_en_preparacion` | centro |
| `carrier_no_retira` | transporte |
| `direccion_invalida` | destino |
| `extravio` | transporte |

Un envío tiene como máximo un motivo. Las causas particionan las cancelaciones logísticas: la suma de las causas es el total de cancelados logísticos.

---

## 5. Estrella gold

```text
                         d_fecha
                            |
d_seller —— d_fc —— f_envios —— d_carrier
                            |
                    d_region / d_comuna
                            |
                 d_estado_envio / d_motivo_cancelacion
```

Un datamart, `dm_fulfillment` (tablas en el futuro `gold_meli`). Mismos dueños (operaciones de fulfillment), mismas preguntas cruzadas (centro vs calle), mismo refresh diario.

### 5.1 Hecho `f_envios`

| | |
|---|---|
| Grano | **1 fila por envío** |
| Clave | `envio_id` (PK, única) |
| Qué no es | No es una fila por evento, ni por ítem, ni por orden |

Columnas que el dashboard trata como el contrato mínimo:

| Columna | Tipo | Significado |
|---|---|---|
| `fecha_promesa` | DATE | Día prometido |
| `fecha_entrega_real` | DATE, nulo | Día real de entrega; nulo si no está entregado |
| `estado` | STRING | Catálogo 4.8 |
| `motivo_cancelacion_logistica` | STRING, nulo | Catálogo 4.8 |
| `fc_id` | STRING | Centro, o `FC_NA` |
| `carrier_id` | STRING | Carrier, o `CARRIER_NA` |
| `region` | STRING | Región de **destino** (`RM`, `VS`, …) |
| `seller_id` | STRING | Seller del envío |

Columnas de soporte (sin ellas las fórmulas no cierran):

| Columna | Tipo | Significado |
|---|---|---|
| `envio_id` | STRING | PK |
| `orden_id` | STRING | Dimensión degenerada. No cambia el grano |
| `comuna_id` | STRING | Destino |
| `tipo_logistica` | STRING | `full`, `flex`, `colecta`, `cross_dock` |
| `ts_creacion` | TIMESTAMP | |
| `ts_despacho` | TIMESTAMP, nulo | |
| `ts_entrega` | TIMESTAMP, nulo | |
| `fecha_creacion` | DATE | `DATE(ts_creacion)` en Santiago |
| `fecha_despacho` | DATE, nulo | |
| `es_entregado` | INT64 0/1 | Alias de fórmula: `entregados` |
| `es_atrasado` | INT64 0/1 | Alias de fórmula: `atrasado` |
| `es_a_tiempo` | INT64 0/1 | Alias de fórmula: `a_tiempo` |
| `es_cancelado_logistica` | INT64 0/1 | Alias de fórmula: `cancelado_logistica` |
| `lead_time_horas` | FLOAT64, nulo | Solo en entregados |
| `lead_time_preparacion_horas` | FLOAT64, nulo | `ts_creacion` → `ts_despacho` |
| `lead_time_transito_horas` | FLOAT64, nulo | `ts_despacho` → `ts_entrega` |
| `n_intentos_fallidos` | INT64 | Eventos `intento_fallido` de ese envío |

`region` en el hecho es destino. La región del centro está en `d_fc`. La del seller, en `d_seller`. No se intercambian.

Invariantes, para la cuarentena del Paso 6:

- `es_entregado = 1` implica `ts_entrega`, `fecha_entrega_real` y `ts_creacion` presentes, y `fecha_entrega_real = DATE(ts_entrega, 'America/Santiago')`.
- `es_a_tiempo + es_atrasado = es_entregado` en cada fila.
- `es_cancelado_logistica = 1` implica un motivo del catálogo, y al revés.
- `es_entregado` y `es_cancelado_logistica` no son 1 a la vez.
- En un entregado con `ts_despacho`, `lead_time_horas = lead_time_preparacion_horas + lead_time_transito_horas`. Por eso las horas salen de `TIMESTAMP_DIFF(..., MINUTE) / 60`: el diff en `HOUR` trunca y los tramos dejan de sumar el total.

Definición de los indicadores, evaluados en la fila del envío:

```text
entregados              = 1 si estado = 'entregado' y fecha_entrega_real no es nula; si no, 0
atrasado                = 1 si entregados = 1 y fecha_entrega_real > fecha_promesa; si no, 0
a_tiempo                = 1 si entregados = 1 y fecha_entrega_real <= fecha_promesa; si no, 0
entregado_con_despacho  = 1 si entregados = 1 y ts_despacho no es nulo; si no, 0
cancelado_logistica     = 1 si estado = 'cancelado_logistica'; si no, 0
cancelado_causa         = 1 si cancelado_logistica = 1 y motivo_cancelacion_logistica = <causa>; si no, 0
envios                  = 1 en cada fila
lead_time_horas         = TIMESTAMP_DIFF(ts_entrega, ts_creacion, MINUTE) / 60 si entregados = 1; si no, NULL
lead_time_preparacion_horas = TIMESTAMP_DIFF(ts_despacho, ts_creacion, MINUTE) / 60 si entregado_con_despacho = 1; si no, NULL
lead_time_transito_horas    = TIMESTAMP_DIFF(ts_entrega, ts_despacho, MINUTE) / 60 si entregado_con_despacho = 1; si no, NULL
```

`SUM(entregados)` es la suma de ese 0/1. No es un porcentaje precalculado y no se promedia.

Partición prevista (Paso 4, no se crea ahora): `PARTITION BY fecha_promesa`, `CLUSTER BY fc_id, carrier_id, region`. La pregunta habitual filtra por la promesa del período.

### 5.2 Dimensiones

| Dim | Grano | Clave | Atributos que el dashboard muestra |
|---|---|---|---|
| `d_fecha` | 1 día | `fecha` | `anio`, `mes`, `semana_iso`, `nombre_dia` |
| `d_seller` | 1 seller | `seller_id` | nombre, `tipo_seller`, `region_origen` |
| `d_fc` | 1 centro, más `FC_NA` | `fc_id` | nombre, `tipo_fc`, `region_fc`, comuna |
| `d_carrier` | 1 carrier, más `CARRIER_NA` | `carrier_id` | nombre, `tipo_servicio` |
| `d_region` | 1 región de destino | `region` | nombre, zona |
| `d_comuna` | 1 comuna | `comuna_id` | nombre, `region` |
| `d_estado_envio` | 1 código de estado | `estado` | nombre visible, orden del hito |
| `d_motivo_cancelacion` | 1 motivo, más fila «no aplica» | `motivo_cancelacion_logistica` | nombre, grupo (`centro`, `transporte`, `destino`) |

`d_fecha` se une por rol: `fecha_promesa`, `fecha_entrega_real`, `fecha_creacion`, `fecha_despacho`. En Looker son cuatro joins, no cuatro copias de la tabla con números distintos.

La fila «no aplica» del motivo absorbe el NULL de los envíos que no se cancelaron por logística, para que un filtro de causa no borre el denominador de los otros KPI por un inner join accidental.

---

## 6. Métricas

Todas se leen desde `f_envios` (o desde un agregado que guarde **sumas**, nunca el porcentaje ya cerrado).

### 6.1 % atrasados vs promesa

```text
% atrasados vs promesa = SUM(atrasado) / SUM(entregados)
```

Denominador: solo entregados. En tránsito, cancelados y devueltos no diluyen el atraso de quienes sí recibieron el paquete.

Si `SUM(entregados) = 0`, el KPI es nulo. No es 0%.

### 6.2 Cumplimiento de promesa

```text
cumplimiento de promesa = SUM(a_tiempo) / SUM(entregados)
```

Con las definiciones de la sección 5.1, sobre el mismo filtro:

```text
cumplimiento de promesa = 1 − % atrasados vs promesa
```

siempre que `SUM(entregados) > 0`. Si las dos tarjetas no suman 100%, hay un filtro distinto o alguien usó `AVG`.

### 6.3 Cancelaciones logísticas por causa

Conteo de la causa, y su participación sobre las cancelaciones logísticas (no sobre todos los envíos):

```text
cancelaciones de la causa = SUM(cancelado_causa)

participación de la causa = SUM(cancelado_causa) / SUM(cancelado_logistica)
```

Tasa de cancelación logística sobre el universo de envíos del filtro (otra pregunta, otro denominador):

```text
tasa de cancelación logística = SUM(cancelado_logistica) / SUM(envios)
```

La participación de las causas suma 1. La tasa no se parte con el mismo denominador: mezclarlas es el error típico («el 40% de los envíos se cae por stock» cuando el 40% es la parte del stock **dentro** de las cancelaciones).

### 6.4 Lead time

```text
lead time (horas) = SUM(lead_time_horas) / SUM(entregados)
```

Tramos, sobre los entregados que tienen despacho (ahí preparación + tránsito = total):

```text
lead time preparación (horas) = SUM(lead_time_preparacion_horas) / SUM(entregado_con_despacho)
lead time tránsito (horas)     = SUM(lead_time_transito_horas) / SUM(entregado_con_despacho)
```

`AVG(lead_time_horas)` solo es válido si cada fila pesa un envío. Desde un agregado semanal o regional se usa `SUM(suma_horas) / SUM(entregados)`. Nunca `AVG(lead_time_promedio)`.

El lead time no es un porcentaje. Cuánto se pasó de la promesa es otra medida, solo en filas `atrasado = 1`. El reloj arranca al inicio del día siguiente a `fecha_promesa` (medianoche Santiago): entregar ese día no es atraso, así que esas horas no entran.

```text
horas_de_atraso = TIMESTAMP_DIFF(
                    ts_entrega,
                    TIMESTAMP_ADD(TIMESTAMP(fecha_promesa, 'America/Santiago'), INTERVAL 1 DAY),
                    MINUTE) / 60
                  si atrasado = 1; si no, NULL

horas de atraso = SUM(horas_de_atraso) / SUM(atrasado)
```

No es la tarjeta principal. La tarjeta principal es el lead time creación → entrega.

### 6.5 Qué no hacer

| Antipatrón | Por qué miente |
|---|---|
| `AVG(pct_atrasados)` por FC, región o semana | Promedio de porcentajes. Un FC chico pesa igual que uno grande. |
| `AVG(es_atrasado)` mezclado con filas no entregadas | El boolean de un envío en tránsito tira el porcentaje hacia abajo. El denominador correcto es `SUM(entregados)`. |
| `AVG(cumplimiento)` guardado en una tabla agregada | Segundo promedio. Hay que guardar `SUM(a_tiempo)` y `SUM(entregados)`. |
| Participación de la causa / `SUM(envios)` vendida como «% de la causa» | Cambia el denominador. La participación es sobre `SUM(cancelado_logistica)`. |
| Contar eventos de tracking como envíos | Infla entregados y atrasos. El grano es `envio_id`. |

---

## 7. Agregado permitido

Si una vista semanal existe para no escanear el hecho entero, guarda aditivos:

`semana`, `fc_id`, `carrier_id`, `region`, `seller_id`, `SUM(entregados)`, `SUM(atrasado)`, `SUM(a_tiempo)`, `SUM(cancelado_logistica)`, `SUM(cancelado_causa)` por motivo, `SUM(lead_time_horas)`, `SUM(envios)`.

El porcentaje se calcula **en el gráfico**, al final del filtro. Guardar `pct_atrasados` en esa vista está permitido solo como columna de auditoría, nunca como métrica de Looker.

---

## 8. Páginas del dashboard futuro

El informe todavía no existe. La guía visual está en [`looker/STYLE_GUIDE.md`](../looker/STYLE_GUIDE.md). Cada página consume solo gold y responde solo lo que dice esta tabla.

| Página | Preguntas que responde | Métricas en la página | Cortes |
|---|---|---|---|
| **Overview** | ¿Cumplimos la promesa en el período? ¿Qué tan atrasados van los entregados? ¿Cuánto tarda un envío y qué parte se cancela por logística? | Cumplimiento de promesa, % atrasados vs promesa, lead time (horas), tasa de cancelación logística | Semana de `fecha_promesa`, FC, región de destino |
| **Atrasos** | ¿El atraso está en un centro, en un carrier o en una región de Chile? ¿Qué semana se rompió? | `% atrasados vs promesa = SUM(atrasado) / SUM(entregados)` en cada celda | FC × semana, carrier, región, `tipo_logistica` |
| **Cancelaciones** | ¿Qué causa domina? ¿En qué seller o FC se concentra? ¿Eso es mucho sobre el total de envíos o solo dentro de las cancelaciones? | `SUM(cancelado_causa)`, participación `SUM(cancelado_causa) / SUM(cancelado_logistica)`, tasa `SUM(cancelado_logistica) / SUM(envios)` | Motivo, grupo del motivo, seller, FC |
| **Lead time** | ¿Cuántas horas van de la creación a la entrega? ¿Se las queda la preparación o el tránsito? | `SUM(lead_time_horas) / SUM(entregados)` y los dos tramos | FC, carrier, región, semana |
| **Drill** | ¿Qué combinación seller × comuna × carrier explica el número del Overview? ¿Hay reintentos detrás del atraso? | Las cuatro métricas de arriba, más `SUM(envios)` y `SUM(n_intentos_fallidos)` | Seller, comuna, carrier, estado |

La serie semanal del Overview usa la semana de `fecha_promesa`, no la de la entrega: la promesa es el compromiso que operaciones miró esa semana. Un envío prometido el viernes y entregado el lunes siguiente cae en la semana de la promesa, y suma como atrasado.

Lo que ninguna de estas páginas responde (a propósito, en este lab):

- ¿La orden completa llegó a tiempo? Exigiría un segundo grano (todas las piezas de la orden) y otra definición. No es `f_envios`.
- Precio, comisión, publicidad, reclamos de compra. Fuera del dominio.
- Tracking GPS. Los eventos son hitos, no posiciones.

---

## 9. Fuera de este paso

- Generador de datos y CSV.
- Proyecto GCP, datasets, DDL, cargas, credenciales.
- Informe de Looker Studio publicado.
- Logos o piezas gráficas de la marca.

**Paso 2:** CSV sintéticos con este grano y este catálogo, y el contrato columna a columna.
