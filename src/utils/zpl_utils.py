"""Helpers de regex e manipulação de strings ZPL."""
from __future__ import annotations

import re

RE_BLOCO_ZPL = re.compile(r"\^XA.*?\^XZ", re.DOTALL)

RE_FD_FIELD = re.compile(r"\^FD(?P<conteudo>.*?)\^FS", re.DOTALL)

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


def extrair_campos_fd(bloco: str) -> list[str]:
    return [m.group("conteudo").strip() for m in RE_FD_FIELD.finditer(bloco)]


def extrair_sku(bloco: str) -> str | None:
    m = RE_SKU.search(bloco)
    if m:
        return m.group("sku").strip().upper()
    m = RE_BARCODE_FIELD.search(bloco)
    if m:
        return m.group("codigo").strip().upper()
    return None


def extrair_descricao(bloco: str, sku: str | None = None) -> str:
    campos = extrair_campos_fd(bloco)
    candidatos = []
    for c in campos:
        if not c:
            continue
        if sku and sku.lower() in c.lower():
            continue
        if re.fullmatch(r"[\d./,\-\sR$xX]+", c):
            continue
        if len(c) < 4:
            continue
        candidatos.append(c)
    if not candidatos:
        return "Sem descricao"
    return max(candidatos, key=len)[:80]


def sanitizar_para_zpl(texto: str) -> str:
    return (
        texto.replace("^", " ")
        .replace("~", "-")
        .replace("\\", "/")
        .strip()
    )
