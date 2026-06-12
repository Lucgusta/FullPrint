"""Integracao com impressora Zebra via win32print (Windows).

Em ambientes sem `pywin32` (Linux/macOS dev), opera em modo simulador:
salva o ZPL em arquivo dentro de `data/dev_output/`. Isso permite que o
projeto rode e seja testado fora do Windows.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..utils.logger import get_logger

log = get_logger("printer")

try:
    import win32print  # type: ignore
    _WIN32_DISPONIVEL = True
except ImportError:
    win32print = None
    _WIN32_DISPONIVEL = False


class PrinterError(RuntimeError):
    pass


class ZebraPrinterService:
    def __init__(
        self,
        encoding: str = "utf-8",
        dev_mode: bool = False,
        dev_output_dir: Path | None = None,
    ) -> None:
        self.encoding = encoding
        self.dev_mode = dev_mode or not _WIN32_DISPONIVEL
        self.dev_output_dir = dev_output_dir or Path("data/dev_output")
        if self.dev_mode:
            log.warning(
                "ZebraPrinterService em DEV_MODE (%s). Saidas serao gravadas em %s",
                "win32print indisponivel" if not _WIN32_DISPONIVEL else "config",
                self.dev_output_dir,
            )

    def listar_impressoras(self) -> list[str]:
        if self.dev_mode or not _WIN32_DISPONIVEL:
            return ["[DEV] Simulador (arquivo)"]
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            impressoras = win32print.EnumPrinters(flags)
            return [p[2] for p in impressoras]
        except Exception as exc:
            log.exception("Falha ao enumerar impressoras: %s", exc)
            return []

    def impressora_padrao(self) -> str | None:
        if self.dev_mode or not _WIN32_DISPONIVEL:
            return "[DEV] Simulador (arquivo)"
        try:
            return win32print.GetDefaultPrinter()
        except Exception as exc:
            log.exception("Falha ao obter impressora padrao: %s", exc)
            return None

    def print_zpl(self, zpl_content: str | bytes, printer_name: str, job_name: str = "ZPL Lote") -> None:
        # Pass-through: quando recebe bytes (conteudo original do arquivo da
        # Shopee), envia sem decode/re-encode — fidelidade byte a byte.
        if isinstance(zpl_content, bytes):
            dados = zpl_content
        else:
            dados = zpl_content.encode(self.encoding, errors="replace")
        if not dados.strip():
            raise PrinterError("Conteudo ZPL vazio.")

        if self.dev_mode or not _WIN32_DISPONIVEL:
            self._gravar_dev(dados, printer_name, job_name)
            return

        try:
            handle = win32print.OpenPrinter(printer_name)
            try:
                doc_info = (job_name, None, "RAW")
                job_id = win32print.StartDocPrinter(handle, 1, doc_info)
                try:
                    win32print.StartPagePrinter(handle)
                    win32print.WritePrinter(handle, dados)
                    win32print.EndPagePrinter(handle)
                finally:
                    win32print.EndDocPrinter(handle)
                log.info("Job %s enviado para %s (%d bytes)", job_id, printer_name, len(dados))
            finally:
                win32print.ClosePrinter(handle)
        except Exception as exc:
            log.exception("Erro ao imprimir: %s", exc)
            raise PrinterError(str(exc)) from exc

    def _gravar_dev(self, dados: bytes, printer_name: str, job_name: str) -> None:
        self.dev_output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in job_name)[:40]
        arquivo = self.dev_output_dir / f"{ts}_{slug}.zpl"
        arquivo.write_bytes(dados)
        log.info(
            "[DEV] %d bytes gravados em %s (impressora simulada: %s)",
            len(dados),
            arquivo,
            printer_name,
        )
