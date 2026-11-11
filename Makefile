# Meli Fulfillment — lab runners
# Uso: make test | make data | make bronze | make run
#       make run DRY=1
#
# make run reconstruye todo desde cero: regenera CSV, CREATE OR REPLACE de
# meli_bronze y load WRITE_TRUNCATE. Después compara num_rows contra
# data/manifest.json e imprime OK o FAIL.
#
# Sandbox (sin facturación): sin DML, sin streaming. Las tablas y las
# particiones expiran a los 60 días; por eso make run no depende de lo que
# haya quedado de la corrida anterior.
#
# Auth: ADC. GCP_PROJECT es obligatorio para bronze/run reales (no hay default).
# DRY=1 no llama a BigQuery. Igual regenera los CSV: son locales y el load
# en dry-run los necesita para validar headers.

PY  ?= python3
DRY ?= 0
ifeq ($(DRY),1)
  DRY_FLAG := --dry-run
else
  DRY_FLAG :=
endif

.PHONY: help test data bronze run

help:
	@echo "Targets: data | bronze | run | test"
	@echo "PY=$(PY)  DRY=$(DRY)"
	@echo "GCP_PROJECT debe estar exportado para bronze y run reales (no hay default)."
	@echo "DRY=1 regenera CSV y valida DDL/headers; no consulta BigQuery."

test:
	$(PY) -m pytest -q

data:
	$(PY) src/generate_data.py

bronze:
	$(PY) src/apply_ddl.py $(DRY_FLAG)
	$(PY) src/load_bronze.py $(DRY_FLAG)

run: data bronze
	$(PY) src/verify_bronze.py $(DRY_FLAG)
