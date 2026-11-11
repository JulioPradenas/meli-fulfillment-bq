"""El one-pager existe y lleva el aviso del lab."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AVISO = "Lab de portafolio. Marca con fines ilustrativos."


def test_onepager_existe_y_tiene_aviso():
    path = ROOT / "site" / "index.html"
    assert path.is_file()
    texto = path.read_text(encoding="utf-8")
    assert AVISO in texto
    assert "captura pendiente" in texto
