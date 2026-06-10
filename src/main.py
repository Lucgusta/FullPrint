"""Ponto de entrada do Shopee ZPL Spooler (MVP)."""
from __future__ import annotations

import sys
from pathlib import Path

# Permite rodar via `python src/main.py` ou como modulo.
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from src.config.settings import load_settings  # type: ignore
    from src.ui.app import ShopeeZPLApp  # type: ignore
    from src.utils.logger import setup_logger  # type: ignore
else:
    from .config.settings import load_settings
    from .ui.app import ShopeeZPLApp
    from .utils.logger import setup_logger


def main() -> int:
    settings = load_settings()
    logger = setup_logger(
        logs_dir=settings.logs_dir,
        level=settings.log_level,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
    )
    logger.info("Iniciando %s v%s", settings.app_name, settings.app_version)
    app = ShopeeZPLApp(settings)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
