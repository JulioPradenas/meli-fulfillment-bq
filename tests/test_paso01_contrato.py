"""Paso 1 — el modelo, la guía y el esqueleto que el CI verifica."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AVISO = "Lab de portafolio. Marca con fines ilustrativos."

README = ROOT / "README.md"
MODELO = ROOT / "docs" / "modelo-datos.md"
GUIA = ROOT / "looker" / "STYLE_GUIDE.md"

# Fórmulas canónicas. Tienen que aparecer igual en el modelo y en la guía.
METRICAS = (
    "f_envios",
    AVISO,
    "SUM(atrasado) / SUM(entregados)",
    "SUM(a_tiempo) / SUM(entregados)",
    "SUM(cancelado_causa) / SUM(cancelado_logistica)",
    "SUM(lead_time_horas) / SUM(entregados)",
    "nunca como promedio de porcentajes",
)


def _texto(path: Path) -> str:
    assert path.is_file(), f"falta {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def test_aviso_en_readme_modelo_y_guia():
    for path in (README, MODELO, GUIA):
        assert AVISO in _texto(path)


def test_modelo_y_guia_contienen_f_envios_metricas_y_aviso():
    for path in (MODELO, GUIA):
        texto = _texto(path)
        faltan = [pieza for pieza in METRICAS if pieza not in texto]
        assert not faltan, f"{path.relative_to(ROOT)} no contiene {faltan}"


def test_modelo_fija_grano_columnas_y_paginas():
    texto = _texto(MODELO)
    for pieza in (
        "1 fila por envío",
        "fecha_promesa",
        "fecha_entrega_real",
        "motivo_cancelacion_logistica",
        "fc_id",
        "carrier_id",
        "seller_id",
        "Overview",
        "Atrasos",
        "Cancelaciones",
        "Lead time",
        "Drill",
    ):
        assert pieza in texto, pieza


def test_guia_fija_paleta_es_cl_y_contraste():
    texto = _texto(GUIA)
    for pieza in ("#FFE600", "#2D3277", "es-CL", "AA", "KPI"):
        assert pieza in texto, pieza


def test_makefile_y_ci_corren_pytest():
    makefile = _texto(ROOT / "Makefile")
    assert "pytest" in makefile
    workflow = _texto(ROOT / ".github" / "workflows" / "pytest.yml")
    assert "push:" in workflow
    assert "pull_request:" in workflow
    assert "make test" in workflow
