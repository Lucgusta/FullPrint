"""Helpers de runtime: deteccao de empacotamento (PyInstaller)."""
from __future__ import annotations

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
