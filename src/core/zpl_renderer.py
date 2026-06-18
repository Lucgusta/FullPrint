"""Renderizador local de ZPL -> imagem (interpreta ZPL II de verdade).

Diferente do ``grf_decoder`` (que apenas decodifica o bitmap ``^GFA`` ja
embutido no arquivo da Shopee), este modulo INTERPRETA o ZPL: texto, fontes,
barcodes, QR, caixas, etc. Isso permite preview fiel de qualquer ZPL — inclusive
o que o proprio app gera (composto/separadora) e ZPL "texto puro" que antes
ficava sem preview.

Implementacao: chama ``renderer/render.mjs`` (Node + zpl-renderer-js/WASM) via
subprocess. Sem Labelary online, sem servidor web — tudo local.

Requisito: Node.js (v18+) instalado e no PATH, ou apontado por
``FULLPRINT_NODE``. O diretorio ``renderer/`` precisa ter ``node_modules``
(``cd renderer && npm install``) — empacotado junto no build.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image

from ..utils.logger import get_logger
from ..utils.runtime import app_dir

log = get_logger("zpl_renderer")

RENDER_TIMEOUT_S = 30

# 203 dpi (Zebra ZD220) = 8 dots/mm; etiqueta padrao Shopee = 10x15 cm.
DEFAULT_DPMM = 8
DEFAULT_WIDTH_MM = 100.0
DEFAULT_HEIGHT_MM = 150.0


class RendererError(RuntimeError):
    """Falha ao renderizar ZPL localmente (Node ausente ou erro de render)."""


@lru_cache(maxsize=1)
def _renderer_dir() -> Path:
    """Localiza a pasta ``renderer/`` (render.mjs + node_modules).

    Cobre os layouts possiveis: empacotado pelo PyInstaller (datas extraidas em
    ``sys._MEIPASS`` ou ao lado do executavel) e desenvolvimento (raiz do repo).
    Retorna o primeiro candidato com ``render.mjs``; senao, o primeiro da lista
    (para a mensagem de erro apontar um caminho plausivel).
    """
    candidatos = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidatos.append(Path(meipass) / "renderer")
    candidatos.append(app_dir() / "renderer")
    candidatos.append(Path(__file__).resolve().parents[2] / "renderer")  # repo (dev)

    for c in candidatos:
        if (c / "render.mjs").exists():
            return c
    return candidatos[0]


def _render_script() -> Path:
    return _renderer_dir() / "render.mjs"


@lru_cache(maxsize=1)
def node_executable() -> str | None:
    """Resolve o caminho do Node, em ordem de prioridade:

    1. ``FULLPRINT_NODE`` (override explicito);
    2. Node instalado JUNTO ao app em ``{app}/node`` (portatil, sem admin) —
       e o que o instalador do Windows baixa quando o usuario aceita;
    3. ``node`` no PATH do sistema.
    """
    override = os.environ.get("FULLPRINT_NODE")
    if override and Path(override).exists():
        return override

    nome = "node.exe" if os.name == "nt" else "node"
    node_home = app_dir() / "node"
    if node_home.is_dir():
        direto = node_home / nome
        if direto.exists():
            return str(direto)
        # O zip oficial extrai numa subpasta (ex.: node-v20.18.1-win-x64/).
        for achado in node_home.glob(f"**/{nome}"):
            return str(achado)

    return shutil.which("node")


def is_available() -> bool:
    """True se da pra renderizar ZPL localmente (Node + script + node_modules)."""
    if node_executable() is None:
        return False
    if not _render_script().exists():
        return False
    if not (_renderer_dir() / "node_modules").exists():
        return False
    return True


def unavailable_reason() -> str | None:
    """Mensagem (PT) explicando por que o render local nao esta disponivel, ou None."""
    if node_executable() is None:
        return (
            "Node.js nao encontrado. Instale em https://nodejs.org "
            "(ou defina FULLPRINT_NODE) para habilitar o preview de ZPL."
        )
    if not _render_script().exists():
        return f"Script do renderer ausente: {_render_script()}"
    if not (_renderer_dir() / "node_modules").exists():
        return (
            "Dependencias do renderer ausentes. Execute: "
            f"cd {_renderer_dir()} && npm install"
        )
    return None


def render_zpl_to_png(
    zpl: str,
    *,
    dpmm: int = DEFAULT_DPMM,
    width_mm: float = DEFAULT_WIDTH_MM,
    height_mm: float = DEFAULT_HEIGHT_MM,
) -> bytes:
    """Interpreta o ``zpl`` e devolve os bytes do PNG renderizado.

    Args:
        zpl:       Codigo ZPL completo (``^XA...^XZ``).
        dpmm:      Dots por mm (8=203dpi, 12=300dpi, 24=600dpi).
        width_mm:  Largura da etiqueta em milimetros.
        height_mm: Altura da etiqueta em milimetros.

    Raises:
        RendererError: Node ausente, script faltando ou falha de renderizacao.
    """
    reason = unavailable_reason()
    if reason is not None:
        raise RendererError(reason)
    if not zpl or not zpl.strip():
        raise RendererError("ZPL vazio: nada para renderizar.")

    node = node_executable()
    assert node is not None  # garantido por unavailable_reason()
    cmd = [node, str(_render_script()), str(int(dpmm)), str(width_mm), str(height_mm)]
    try:
        result = subprocess.run(
            cmd,
            input=zpl.encode("utf-8"),
            capture_output=True,
            timeout=RENDER_TIMEOUT_S,
        )
    except FileNotFoundError as exc:  # node sumiu entre o check e a chamada
        raise RendererError("Node.js nao encontrado ao executar o renderer.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RendererError(
            f"Renderizacao excedeu {RENDER_TIMEOUT_S}s (ZPL muito grande?)."
        ) from exc

    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace").strip()
        raise RendererError(f"Falha ao renderizar ZPL: {err or 'erro desconhecido'}")
    if not result.stdout:
        raise RendererError("Renderizador nao devolveu imagem (saida vazia).")
    return result.stdout


def render_zpl_to_image(
    zpl: str,
    *,
    dpmm: int = DEFAULT_DPMM,
    width_mm: float = DEFAULT_WIDTH_MM,
    height_mm: float = DEFAULT_HEIGHT_MM,
) -> Image.Image:
    """Igual a :func:`render_zpl_to_png`, mas devolve uma ``PIL.Image`` pronta
    para o preview da UI (a janela usa ``CTkImage`` sobre ``PIL.Image``)."""
    png = render_zpl_to_png(zpl, dpmm=dpmm, width_mm=width_mm, height_mm=height_mm)
    img = Image.open(io.BytesIO(png))
    img.load()  # materializa antes do buffer sair de escopo
    return img


def render_for_model(zpl: str, modelo) -> Image.Image:
    """Renderiza ``zpl`` usando a geometria/resolucao de um ``LabelModel``.

    Conveniencia para o preview composto: usa as dimensoes e o dpi do modelo
    ativo, garantindo que o preview saia na mesma escala da impressao.
    """
    dpmm = max(1, round(getattr(modelo, "dpi", 203) / 25.4))
    return render_zpl_to_image(
        zpl,
        dpmm=dpmm,
        width_mm=float(getattr(modelo, "largura_mm", DEFAULT_WIDTH_MM)),
        height_mm=float(getattr(modelo, "altura_mm", DEFAULT_HEIGHT_MM)),
    )
