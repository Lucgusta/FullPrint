"""Fila de impressao consumida por uma thread daemon."""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Callable

from ..utils.logger import get_logger
from .printer import PrinterError, ZebraPrinterService

log = get_logger("worker")


@dataclass
class PrintJob:
    printer_name: str
    job_name: str = "ZPL Lote"
    zpl_content: str | None = None
    # Builder lazy: a montagem do ZPL ocorre na thread do worker, mantendo
    # a UI livre quando o lote tem milhares de etiquetas.
    builder: Callable[[], str] | None = None


_SENTINEL = object()

StatusCallback = Callable[[str, str], None]  # (level, mensagem)


class PrintQueueManager:
    def __init__(
        self,
        printer_service: ZebraPrinterService,
        status_callback: StatusCallback | None = None,
    ) -> None:
        self.printer_service = printer_service
        self.status_callback = status_callback or (lambda level, msg: None)
        self._queue: "queue.Queue[object]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="PrintWorker")
        self._thread.start()
        log.info("PrintQueueManager iniciado.")

    def stop(self, timeout: float = 2.0) -> None:
        if not self._thread:
            return
        self._stop_event.set()
        self._queue.put(_SENTINEL)
        self._thread.join(timeout=timeout)
        log.info("PrintQueueManager finalizado.")

    def submit(self, job: PrintJob) -> None:
        self._queue.put(job)
        self.status_callback("info", f"Job enfileirado para {job.printer_name}")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            item = self._queue.get()
            try:
                if item is _SENTINEL:
                    break
                job: PrintJob = item  # type: ignore[assignment]
                try:
                    zpl = job.zpl_content
                    if zpl is None and job.builder is not None:
                        zpl = job.builder()
                    if not zpl:
                        raise PrinterError("Job sem conteudo ZPL.")
                    self.printer_service.print_zpl(zpl, job.printer_name, job.job_name)
                    self.status_callback("ok", f"Impressao concluida: {job.job_name}")
                except PrinterError as exc:
                    self.status_callback("erro", f"Falha na impressao: {exc}")
                except Exception as exc:  # noqa: BLE001
                    log.exception("Erro inesperado no worker")
                    self.status_callback("erro", f"Erro inesperado: {exc}")
            finally:
                self._queue.task_done()
