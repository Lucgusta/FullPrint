"""Helpers de regex para ZPL texto (formato antigo, com ^FD legivel)."""
from __future__ import annotations

import re

RE_BLOCO_ZPL = re.compile(r"\^XA.*?\^XZ", re.DOTALL)

RE_SKU = re.compile(
    r"(?:SKU|sku)\s*[:#]?\s*(?P<sku>[A-Z0-9][A-Z0-9._\-/]{2,40})",
    re.IGNORECASE,
)

RE_BARCODE_FIELD = re.compile(
    r"\^B[CY3]N?,?[^\^]*\^FD(?P<codigo>[A-Z0-9._\-/]{4,40})\^FS",
    re.IGNORECASE,
)


def extrair_blocos(conteudo: str) -> list[str]:
    return RE_BLOCO_ZPL.findall(conteudo)


def extrair_sku(bloco: str) -> str | None:
    m = RE_SKU.search(bloco)
    if m:
        return m.group("sku").strip().upper()
    m = RE_BARCODE_FIELD.search(bloco)
    if m:
        return m.group("codigo").strip().upper()
    return None
