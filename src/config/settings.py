"""Carrega e valida o `config.yaml` do projeto."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..version import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = Path(__file__).with_name("config.yaml")


@dataclass
class Settings:
    app_name: str
    app_version: str
    theme: str
    color_theme: str
    printer_default: str
    printer_encoding: str
    printer_chunk_size: int
    printer_dev_mode: bool
    printer_dev_output_dir: Path
    default_input_dir: Path
    logs_dir: Path
    log_level: str = "INFO"
    log_max_bytes: int = 1_048_576
    log_backup_count: int = 5


def _resolve(path_str: str) -> Path:
    p = Path(os.path.expanduser(path_str))
    return p if p.is_absolute() else (PROJECT_ROOT / p)


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or CONFIG_FILE
    with path.open("r", encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    app = raw.get("app", {})
    printer = raw.get("printer", {})
    paths = raw.get("paths", {})
    logging_cfg = raw.get("logging", {})

    return Settings(
        app_name=app.get("name", "Shopee ZPL Spooler"),
        # Versao vem sempre de src/version.py (fonte unica, injetada pelo CI no
        # build). O campo `version` do config.yaml e ignorado para evitar drift.
        app_version=__version__,
        theme=app.get("theme", "dark"),
        color_theme=app.get("color_theme", "blue"),
        printer_default=printer.get("default_name", ""),
        printer_encoding=printer.get("encoding", "utf-8"),
        printer_chunk_size=int(printer.get("chunk_size", 50)),
        printer_dev_mode=bool(printer.get("dev_mode", False)),
        printer_dev_output_dir=_resolve(printer.get("dev_output_dir", "data/dev_output")),
        default_input_dir=_resolve(paths.get("default_input_dir", "~/Downloads")),
        logs_dir=_resolve(paths.get("logs_dir", "logs")),
        log_level=logging_cfg.get("level", "INFO"),
        log_max_bytes=int(logging_cfg.get("max_bytes", 1_048_576)),
        log_backup_count=int(logging_cfg.get("backup_count", 5)),
    )
