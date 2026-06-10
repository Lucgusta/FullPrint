"""Janela principal da aplicacao (CustomTkinter)."""
from __future__ import annotations

import customtkinter as ctk

from ..config.settings import Settings
from ..services.printer import ZebraPrinterService
from ..services.spooler_worker import PrintQueueManager
from .views.main_view import MainView


class ShopeeZPLApp(ctk.CTk):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

        ctk.set_appearance_mode(settings.theme)
        ctk.set_default_color_theme(settings.color_theme)

        self.title(f"{settings.app_name} v{settings.app_version}")
        self.geometry("1100x680")
        self.minsize(960, 600)

        self.printer_service = ZebraPrinterService(
            encoding=settings.printer_encoding,
            dev_mode=settings.printer_dev_mode,
            dev_output_dir=settings.printer_dev_output_dir,
        )

        self.main_view = MainView(self, settings, self.printer_service, worker=None)  # type: ignore[arg-type]
        self.worker = PrintQueueManager(
            self.printer_service,
            status_callback=lambda level, msg: self.after(0, self.main_view.log_status, level, msg),
        )
        self.main_view.worker = self.worker
        self.worker.start()

        self.main_view.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        self.worker.stop()
        self.destroy()
