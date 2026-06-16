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


# Geometria do sticker em torno do QR (calibrada na folha real 816x1218:
# QRs de ~172px com pitch vertical de ~236px -> ~64px de texto abaixo do QR;
# colunas separadas por gap de apenas ~8px, dai a margem lateral pequena).
CROP_MARGEM_X = 8
CROP_MARGEM_TOPO = 4
CROP_ALTURA_TEXTO = 58


def _crop_clampado(imagem: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
    img_w, img_h = imagem.size
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = max(1, min(w, img_w - x))
    h = max(1, min(h, img_h - y))
    return imagem.crop((x, y, x + w, y + h))


def crop_sticker(folha: Image.Image, st: StickerInfo) -> Image.Image:
    """Recorta um sticker da folha, ancorado na posicao do QR.

    Nao assume grade fixa: o recorte e o retangulo do QR expandido para os
    lados (texto e pouco mais largo que o QR) e para baixo (4 linhas de
    texto: Seller SKU, SKU e descricao em 2 linhas).
    """
    return _crop_clampado(
        folha,
        st.qr_left - CROP_MARGEM_X,
        st.qr_top - CROP_MARGEM_TOPO,
        st.qr_width + 2 * CROP_MARGEM_X,
        st.qr_height + CROP_MARGEM_TOPO + CROP_ALTURA_TEXTO,
    )


# Quiet zone (margem branca) ao redor do QR para manter legibilidade.
CROP_QR_QUIET = 6


def crop_qr(folha: Image.Image, st: StickerInfo) -> Image.Image:
    """Recorta apenas o QR (com quiet zone) — para reposicionar no layout novo."""
    return _crop_clampado(
        folha,
        st.qr_left - CROP_QR_QUIET,
        st.qr_top - CROP_QR_QUIET,
        st.qr_width + 2 * CROP_QR_QUIET,
        st.qr_height + 2 * CROP_QR_QUIET,
    )


def crop_texto(folha: Image.Image, st: StickerInfo) -> Image.Image:
    """Recorta o bloco de texto (Seller SKU, SKU, descricao) logo abaixo do QR.

    Mesma largura do QR (o texto da Shopee fica na coluna do QR, sem invadir
    a coluna vizinha). O renderizador apara o espaco branco depois.
    """
    return _crop_clampado(
        folha,
        st.qr_left - CROP_MARGEM_X,
        st.qr_top + st.qr_height,
        st.qr_width + 2 * CROP_MARGEM_X,
        CROP_ALTURA_TEXTO,
    )


# Distancia (px, abaixo do fim do QR) onde COMECA a descricao do produto. As
# ~2 primeiras linhas do bloco sao Seller SKU + SKU Shopee, que o renderizador
# agora re-escreve como texto nativo (nitido); a descricao (ultimas ~2 linhas)
# nao temos como texto confiavel, entao seguimos recortando-a do bitmap.
# Calibrado na folha real (816x1218): ~64px de texto / 4 linhas -> ~16px/linha.
CROP_DESCRICAO_TOPO = 28


def crop_descricao(folha: Image.Image, st: StickerInfo) -> Image.Image:
    """Recorta SO as linhas de descricao do produto (abaixo do Seller SKU/SKU).

    Diferente de :func:`crop_texto`, pula a faixa superior (Seller SKU + SKU
    Shopee), que passa a ser renderizada como texto nativo. Sobra a descricao,
    que so existe rasterizada no bitmap da Shopee.
    """
    return _crop_clampado(
        folha,
        st.qr_left - CROP_MARGEM_X,
        st.qr_top + st.qr_height + CROP_DESCRICAO_TOPO,
        st.qr_width + 2 * CROP_MARGEM_X,
        CROP_ALTURA_TEXTO - CROP_DESCRICAO_TOPO,
    )


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
