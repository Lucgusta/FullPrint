"""Helpers de runtime: deteccao de empacotamento (PyInstaller) e Tesseract embutido.

Quando o app roda como `.exe` gerado pelo PyInstaller, o instalador (Inno Setup)
coloca o Tesseract OCR portatil em `<pasta-do-exe>/tesseract/`. Aqui apontamos o
`pytesseract` para esse binario embutido, de modo que a maquina do operador NAO
precise ter o Tesseract instalado separadamente.

Em desenvolvimento (rodando do codigo-fonte) nada disso se aplica: o OCR cai para
o `tesseract` do PATH, como antes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True quando rodando como executavel PyInstaller (app instalado)."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Diretorio base da aplicacao.

    - Empacotado (PyInstaller): pasta onde esta o executavel.
    - Desenvolvimento: raiz do repositorio.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundled_tesseract_dir() -> Path | None:
    """Retorna a pasta do Tesseract embutido se o binario existir, senao None."""
    d = app_dir() / "tesseract"
    return d if (d / "tesseract.exe").exists() else None


_TESSERACT_CONFIGURADO = False


def configure_tesseract() -> bool:
    """Aponta o pytesseract para o Tesseract embutido, se houver.

    Retorna True se configurou o binario embutido; False se nao ha bundle
    (o chamador deve entao tentar o Tesseract do PATH).
    """
    global _TESSERACT_CONFIGURADO
    if _TESSERACT_CONFIGURADO:
        return True
    d = bundled_tesseract_dir()
    if not d:
        return False
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = str(d / "tesseract.exe")
    except Exception:  # noqa: BLE001 - pytesseract pode nem estar disponivel
        return False
    tessdata = d / "tessdata"
    if tessdata.exists():
        os.environ["TESSDATA_PREFIX"] = str(tessdata)
    _TESSERACT_CONFIGURADO = True
    return True
