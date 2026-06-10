"""Logger central com rotação de arquivo."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


_INITIALIZED = False


def setup_logger(
    logs_dir: Path,
    level: str = "INFO",
    max_bytes: int = 1_048_576,
    backup_count: int = 5,
) -> logging.Logger:
    global _INITIALIZED
    logs_dir.mkdir(parents=True, exist_ok=True)
    logfile = logs_dir / "spooler.log"

    root = logging.getLogger("shopee_zpl")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if _INITIALIZED:
        return root

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        logfile, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    root.propagate = False

    _INITIALIZED = True
    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"shopee_zpl.{name}")
