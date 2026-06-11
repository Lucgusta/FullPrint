"""Decodifica etiquetas GRF Z64 (Shopee Full) e extrai SKU/posicao via QR code.

Estrutura tipica de UMA "folha" no TXT da Shopee Full:

    ~DGR:DEMO.GRF,124236,102,:Z64:<base64-zlib>:<crc16>
    ^XA...^XGR:DEMO.GRF,1,1^FS^PQ1,0,0,N^XZ
    ^XA^IDR:DEMO.GRF^FS^XZ

Cada GRF contem ate ~10 stickers numa grade 2 colunas x 5 linhas. ATENCAO:
GRFs misturam stickers de SKUs DIFERENTES (verificado empiricamente em ~23%
do arquivo de teste). Por isso retornamos uma lista de stickers por GRF,
nao 1 SKU "principal".
"""
from __future__ import annotations

import base64
import re
import zlib
from dataclasses import dataclass, field

from PIL import Image
from pyzbar import pyzbar

from ..utils.logger import get_logger

log = get_logger("grf_decoder")

RE_TRIO_GRF = re.compile(
    r"(~DG(?P<nome>[^,]+),(?P<total>\d+),(?P<row>\d+),:Z64:(?P<b64>[A-Za-z0-9+/=]+):(?P<crc>[0-9A-Fa-f]+))"
    r"(?P<sep1>\s*)"
    r"(?P<print>\^XA[^~]*?\^XGR:[^,]+,\d+,\d+\^FS[^~]*?\^XZ)"
    r"(?P<sep2>\s*)"
    r"(?P<delete>\^XA\^IDR:[^^]+\^FS\^XZ)",
    re.DOTALL,
)


@dataclass
class StickerInfo:
    """Um QR individual dentro do GRF — corresponde a UM sticker imprimivel."""
    sku: str
    qr_left: int
    qr_top: int
    qr_width: int
    qr_height: int


@dataclass
class EtiquetaGRF:
    """Uma "folha" GRF: o ZPL bruto + bitmap + lista de stickers detectados."""
    indice: int
    nome_grf: str
    largura: int
    altura: int
    zpl_raw: str
    imagem: Image.Image
    stickers: list[StickerInfo] = field(default_factory=list)


def _decodificar_z64(b64: str) -> bytes:
    return zlib.decompress(base64.b64decode(b64))


def _grf_para_imagem(grf: bytes, row_bytes: int) -> Image.Image:
    width = row_bytes * 8
    height = len(grf) // row_bytes
    img = Image.frombytes("1", (width, height), grf)
    # ZPL GRF: bit 1 = tinta (preto). PIL "1" frombytes: bit 1 = branco.
    return img.point(lambda p: 0 if p > 0 else 255).convert("1")


def _detectar_stickers(img: Image.Image) -> list[StickerInfo]:
    stickers: list[StickerInfo] = []
    for c in pyzbar.decode(img):
        if c.type != "QRCODE":
            continue
        sku = c.data.decode("ascii", errors="replace")
        stickers.append(
            StickerInfo(
                sku=sku,
                qr_left=c.rect.left,
                qr_top=c.rect.top,
                qr_width=c.rect.width,
                qr_height=c.rect.height,
            )
        )
    # Ordena top-to-bottom, left-to-right (ordem de leitura)
    stickers.sort(key=lambda s: (s.qr_top, s.qr_left))
    return stickers


def extrair_etiquetas(conteudo: str) -> list[EtiquetaGRF]:
    """Decodifica cada GRF do TXT e detecta seus QRs (stickers internos)."""
    etiquetas: list[EtiquetaGRF] = []
    for idx, m in enumerate(RE_TRIO_GRF.finditer(conteudo), start=1):
        total = int(m["total"])
        row = int(m["row"])
        try:
            grf = _decodificar_z64(m["b64"])
        except Exception as exc:  # noqa: BLE001
            log.warning("GRF #%d: falha Z64 (%s)", idx, exc)
            continue
        if len(grf) != total:
            log.debug("GRF #%d: tamanho descomprimido %d != %d", idx, len(grf), total)
        try:
            img = _grf_para_imagem(grf, row)
        except Exception as exc:  # noqa: BLE001
            log.warning("GRF #%d: falha render (%s)", idx, exc)
            continue

        try:
            stickers = _detectar_stickers(img)
        except Exception as exc:  # noqa: BLE001
            log.warning("GRF #%d: falha decodificar QRs (%s)", idx, exc)
            stickers = []

        etiquetas.append(
            EtiquetaGRF(
                indice=idx,
                nome_grf=m["nome"],
                largura=row * 8,
                altura=len(grf) // row,
                zpl_raw=m.group(0),
                imagem=img,
                stickers=stickers,
            )
        )
    log.info("GRF: %d folhas, %d stickers totais", len(etiquetas), sum(len(e.stickers) for e in etiquetas))
    return etiquetas


def has_grf_z64(conteudo: str) -> bool:
    return "~DG" in conteudo and ":Z64:" in conteudo
