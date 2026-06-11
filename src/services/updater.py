"""Auto-update via GitHub Releases.

Fluxo (apenas quando rodando como `.exe` instalado):
  1. Ao abrir, em thread separada, consulta a Release mais recente no GitHub.
  2. Se a tag for maior que a versao local, baixa o `FullPrintSetup.exe` para %TEMP%.
  3. Ao FECHAR o app, executa o instalador em modo silencioso; o Inno Setup
     substitui a versao instalada (mesmo AppId = upgrade in-place).

Tudo aqui e best-effort: qualquer falha (sem rede, GitHub fora, etc.) e apenas
logada e ignorada -- nunca impede o app de abrir ou fechar.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Callable

from packaging.version import InvalidVersion, Version

from ..utils.logger import get_logger
from ..version import __version__

log = get_logger("updater")

GITHUB_REPO = "LeandroBossiniSoleira/FullPrint"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ASSET_NAME = "FullPrintSetup.exe"
_USER_AGENT = "FullPrint-Updater"
_TIMEOUT_API = 10
_TIMEOUT_DOWNLOAD = 120


class UpdateInfo:
    def __init__(self, version: str, download_url: str) -> None:
        self.version = version
        self.download_url = download_url


def _http_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=_TIMEOUT_API) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_for_update() -> UpdateInfo | None:
    """Retorna UpdateInfo se houver versao mais nova publicada; senao None.

    Nunca levanta excecao.
    """
    try:
        data = _http_json(RELEASES_API)
        tag = (data.get("tag_name") or "").lstrip("vV")
        if not tag:
            return None
        try:
            if Version(tag) <= Version(__version__):
                return None
        except InvalidVersion:
            log.warning("Versao invalida ao comparar: tag=%r atual=%r", tag, __version__)
            return None

        asset_url = next(
            (
                a.get("browser_download_url")
                for a in data.get("assets", [])
                if a.get("name") == ASSET_NAME
            ),
            None,
        )
        if not asset_url:
            log.warning("Release %s nao possui asset %s", tag, ASSET_NAME)
            return None

        log.info("Atualizacao disponivel: %s -> %s", __version__, tag)
        return UpdateInfo(tag, asset_url)
    except Exception as exc:  # noqa: BLE001 - update e best-effort
        log.info("Verificacao de update falhou (ignorado): %s", exc)
        return None


def download_installer(info: UpdateInfo) -> Path | None:
    """Baixa o instalador para %TEMP%. Retorna o caminho ou None em caso de falha."""
    try:
        dest = Path(tempfile.gettempdir()) / f"FullPrintSetup-{info.version}.exe"
        req = urllib.request.Request(info.download_url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=_TIMEOUT_DOWNLOAD) as resp, dest.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
        log.info("Instalador da versao %s baixado em %s", info.version, dest)
        return dest
    except Exception as exc:  # noqa: BLE001
        log.warning("Falha ao baixar instalador: %s", exc)
        return None


def check_and_download_async(on_ready: Callable[[Path], None]) -> threading.Thread:
    """Em thread daemon: verifica e (se houver) baixa o instalador.

    Chama `on_ready(caminho_do_instalador)` quando o download termina. O callback
    roda na thread do updater -- a UI deve reagendar para a main thread (ex.:
    `self.after(0, ...)`).
    """

    def _run() -> None:
        info = check_for_update()
        if not info:
            return
        path = download_installer(info)
        if path:
            on_ready(path)

    t = threading.Thread(target=_run, daemon=True, name="fullprint-updater")
    t.start()
    return t


def run_installer_silent(installer_path: Path) -> bool:
    """Dispara o instalador em modo silencioso (Windows). Retorna True se iniciou.

    Deve ser chamado no fechamento do app; o instalador fecha o que sobrar do
    processo (`/CLOSEAPPLICATIONS`) e faz o upgrade in-place.
    """
    try:
        subprocess.Popen(
            [str(installer_path), "/SILENT", "/NORESTART", "/CLOSEAPPLICATIONS"],
            close_fds=True,
        )
        log.info("Instalador silencioso iniciado: %s", installer_path)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Falha ao iniciar instalador: %s", exc)
        return False
