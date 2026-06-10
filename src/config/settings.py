"""Carrega e valida o `config.yaml` do projeto."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = Path(__file__).with_name("config.yaml")


@dataclass
class LabelModel:
    id: str
    nome: str
    largura_dots: int
    altura_dots: int


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
    templates_dir: Path
    logs_dir: Path
    label_models: list[LabelModel] = field(default_factory=list)
    log_level: str = "INFO"
    log_max_bytes: int = 1_048_576
    log_backup_count: int = 5

    def label_model_by_id(self, model_id: str) -> LabelModel | None:
        for m in self.label_models:
            if m.id == model_id:
                return m
        return None


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

    models = [
        LabelModel(
            id=m["id"],
            nome=m["nome"],
            largura_dots=int(m["largura_dots"]),
            altura_dots=int(m["altura_dots"]),
        )
        for m in raw.get("label_models", [])
    ]

    return Settings(
        app_name=app.get("name", "Shopee ZPL Spooler"),
        app_version=app.get("version", "0.1.0"),
        theme=app.get("theme", "dark"),
        color_theme=app.get("color_theme", "blue"),
        printer_default=printer.get("default_name", ""),
        printer_encoding=printer.get("encoding", "utf-8"),
        printer_chunk_size=int(printer.get("chunk_size", 50)),
        printer_dev_mode=bool(printer.get("dev_mode", False)),
        printer_dev_output_dir=_resolve(printer.get("dev_output_dir", "data/dev_output")),
        default_input_dir=_resolve(paths.get("default_input_dir", "~/Downloads")),
        templates_dir=_resolve(paths.get("templates_dir", "src/core/templates")),
        logs_dir=_resolve(paths.get("logs_dir", "logs")),
        label_models=models,
        log_level=logging_cfg.get("level", "INFO"),
        log_max_bytes=int(logging_cfg.get("max_bytes", 1_048_576)),
        log_backup_count=int(logging_cfg.get("backup_count", 5)),
    )
