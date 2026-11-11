# Meli — Fulfillment de marketplace en BigQuery

> **Lab de portafolio. Marca con fines ilustrativos.**  
> No es un entregable de empleo ni un claim sobre Mercado Libre. Sin logos.

Analista: [Julio Pradenas](https://github.com/JulioPradenas)

Proyecto 2 del portafolio Analista BI.  
Proyecto 1: [kora-logistica-bq](https://github.com/JulioPradenas/kora-logistica-bq) (WMS + last mile).

## Objetivo

Un solo número (SSoT) para el cumplimiento de la **promesa de entrega** de un marketplace de fulfillment estilo Mercado Libre, en Chile: atrasos contra la fecha prometida, cancelaciones logísticas por causa y lead time, con grano **un envío**.

## Problema

Operaciones mira la promesa en un export de envíos, el tracking en otro y al seller en una planilla. El «% atrasados» de un FC no se puede sumar con el de otro porque alguien promedió porcentajes. No hay forma de decir si el atraso se fue en el centro de fulfillment o en el carrier, ni qué causa cancela de verdad.

## Preguntas de negocio

1. De los envíos **entregados**, ¿qué porcentaje llegó después de la fecha promesa?
2. ¿Cuál es el cumplimiento de promesa del período (a tiempo / entregados), y cómo se mueve por semana?
3. ¿Qué causas explican las cancelaciones logísticas, y en qué seller o FC se concentran?
4. ¿Cuál es el lead time real (creación → entrega) y qué tramo se lo queda: preparación o tránsito?
5. ¿El incumplimiento de un seller se explica por el FC que lo opera o por la comuna de destino?

Fórmulas cerradas (SUM/SUM, nunca promedio de porcentajes): [docs/modelo-datos.md](docs/modelo-datos.md).

## Solución (sandbox, por construir)

```text
CSV sintéticos → Python (laptop) → BigQuery bronze → silver → gold
                                                              ↓
                                                        Looker Studio
                                                        (f_envios + dims)
```

- **Hecho gold:** `f_envios` — 1 fila por envío. Se materializa en un paso posterior.
- **Proyecto GCP:** el de la variable `GCP_PROJECT` (en este lab, `meli-fulfillment-jp`). El código no trae un proyecto por defecto.
- **Bronze:** dataset `meli_bronze`, location `US`. Sandbox sin facturación; los datos son sintéticos y no hay requisito de residencia en Chile.
- **Zona horaria de los hechos:** `America/Santiago`.
- **Expiración:** tablas y particiones a **60 días**. `make run` reconstruye todo desde cero.

Cloud Scheduler / Cloud Functions / Composer: solo se narrarán en pasos posteriores. No hay credenciales en este repo.

## Roadmap

| Paso | Entrega | Estado |
|---|---|---|
| 1 | Esqueleto, modelo de datos, guía de estilo | ✅ |
| 2 | CSV sintéticos, anomalías y bronze sandbox | ✅ |
| 3 | Silver (cuarentena) | ⏳ |
| 4 | Gold `f_envios` + dimensiones | ⏳ |
| 5 | Demo de partition / cluster | ⏳ |
| 6 | Looker Studio según la guía de estilo | ⏳ |
| 7 | One-pager de portafolio | ⏳ |

El bronze ya está definido (Paso 2). Silver y gold siguen fuera: cuando existan, también serán `CREATE OR REPLACE … AS SELECT`, sin DML, con particiones que expiran a los 60 días.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make test
```

`make test` corre pytest. No llama a BigQuery.

## Paso 2 — correrlo en la Mac

El proyecto `meli-fulfillment-jp` está en **BigQuery sandbox, sin facturación**. No hay DML (`INSERT` / `UPDATE` / `DELETE` / `MERGE`) ni streaming inserts. El camino permitido es load job `WRITE_TRUNCATE` y `CREATE OR REPLACE`. Las tablas y las particiones **expiran a los 60 días**; no hace falta conservarlas. `make run` regenera los CSV, reemplaza el schema y vuelve a cargar.

```bash
gcloud auth application-default login
export GCP_PROJECT=meli-fulfillment-jp
make run
```

`GCP_PROJECT` es obligatorio. Si falta, el script se detiene y lo dice: no hay proyecto por defecto. Auth solo con ADC. No uses una llave de service account.

Sin tocar GCP (valida CSV, DDL y headers, y compara manifest contra CSV):

```bash
make data          # escribe data/raw/*.csv y data/manifest.json
make run DRY=1     # regenera CSV + dry-run de DDL, load y verificación
```

Detalle, conteos y anomalías: [docs/paso-02-bronze.md](docs/paso-02-bronze.md).

## Docs

- [Modelo de datos](docs/modelo-datos.md) — fuentes, `f_envios`, fórmulas, páginas del dashboard
- [Paso 2 — bronze sandbox](docs/paso-02-bronze.md) — CSV, anomalías, load job, límite de 60 días
- [Guía de estilo Looker Studio](looker/STYLE_GUIDE.md) — paleta, layout, KPI cards, es-CL, contraste AA

## Disclaimer

Lab de portafolio. Marca con fines ilustrativos. El bronze es sintético y el sandbox lo borra a los 60 días. Silver, gold y Looker Studio siguen en los pasos siguientes.
