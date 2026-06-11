"""OCR de descricao e Seller SKU a partir do bitmap GRF, por QR especifico.

A area de texto abaixo de cada QR tem 4 linhas:
    Seller SKU: K-...        <- OCR como sugestao (~85% certo, depende da fonte)
    SKU: 25192...             <- redundante (ja temos do QR), descartado
    Descricao linha 1         <- OCR (texto longo redundante, recuperavel)
    Descricao linha 2         <- OCR

Como GRFs PODEM misturar stickers de SKUs diferentes (verificado), o OCR
DEVE rodar abaixo do QR ESPECIFICO do SKU desejado, nao do "1o QR da folha".

Tesseract precisa estar instalado no sistema (binario `tesseract` no PATH
e idioma 'por'). Sem ele, OCR retorna string vazia.
"""
from __future__ import annotations

import re
import shutil
from collections import Counter

from PIL import Image, ImageFilter, ImageOps

from ..utils.logger import get_logger
from .grf_decoder import StickerInfo

log = get_logger("ocr")

_TESSERACT_DISPONIVEL: bool | None = None
# Pixels abaixo do QR onde a area da descricao comeca. Calibrado empiricamente
# (offset 12 pula as 2 linhas de SKU sem cortar a 1a linha de descricao).
LINHAS_SKU_PX = 12
# Altura aprox em pixels da area de descricao (2 linhas wrapadas).
ALTURA_DESCRICAO_PX = 30
# Altura aprox da linha de Seller SKU (logo abaixo do QR).
ALTURA_SELLER_PX = 14


def _tem_tesseract() -> bool:
    global _TESSERACT_DISPONIVEL
    if _TESSERACT_DISPONIVEL is None:
        _TESSERACT_DISPONIVEL = shutil.which("tesseract") is not None
        if not _TESSERACT_DISPONIVEL:
            log.warning(
                "Tesseract nao encontrado no PATH. OCR desabilitado;"
                " descricao ficara vazia."
            )
    return _TESSERACT_DISPONIVEL


def _preprocessar(crop: Image.Image) -> Image.Image:
    w, h = crop.size
    img = crop.convert("L").resize((w * 5, h * 5), Image.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2))
    img = ImageOps.autocontrast(img, cutoff=2)
    return img


def _limpar_descricao(texto: str) -> str:
    linhas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    # Descarta qualquer linha onde OCR detectou "SKU" (Seller SKU + SKU numerico).
    descricoes = [ln for ln in linhas if "sku" not in ln.lower()]
    if not descricoes:
        return ""
    return " ".join(descricoes)[:120].strip()


def _crop_clampado(imagem: Image.Image, x: int, y: int, w: int, h: int) -> Image.Image:
    img_w, img_h = imagem.size
    x = max(0, min(x, img_w - 1))
    y = max(0, min(y, img_h - 1))
    w = max(1, min(w, img_w - x))
    h = max(1, min(h, img_h - y))
    return imagem.crop((x, y, x + w, y + h))


def ocr_descricao_at(imagem: Image.Image, sticker: StickerInfo) -> str:
    """Roda OCR na area de texto abaixo do QR `sticker` e retorna a descricao."""
    if not _tem_tesseract():
        return ""
    crop = _crop_clampado(
        imagem,
        sticker.qr_left,
        sticker.qr_top + sticker.qr_height + LINHAS_SKU_PX,
        sticker.qr_width,
        ALTURA_DESCRICAO_PX,
    )
    pre = _preprocessar(crop)
    try:
        import pytesseract
        bruto = pytesseract.image_to_string(pre, lang="por", config="--psm 6")
    except Exception as exc:  # noqa: BLE001
        log.warning("Falha OCR descricao: %s", exc)
        return ""
    return _limpar_descricao(bruto)


def _isolar_seller_sku(s: str) -> str:
    """Remove prefixo 'Seller SKU:' garbled e isola a parte tipo `K-XXX-YYY`."""
    s = s.replace(" ", "")
    # Procura primeira ocorrencia de [LETRA]-[LETRA/DIGITO] que nao seja "SKU"
    m = re.search(r"[A-Z][A-Z]?-[A-Z0-9]", s)
    if m:
        return s[m.start():]
    return s


def ocr_seller_sku_at(
    imagem: Image.Image,
    stickers: list[StickerInfo],
    max_amostras: int = 8,
) -> str:
    """OCR multi-voto: usa ate `max_amostras` ocorrencias do mesmo SKU para
    extrair o Seller SKU via voto majoritario por posicao.

    Acuracia tipica ~85-95% depending on font. Eh uma SUGESTAO editavel; o
    usuario corrige via duplo-clique e o resultado vira cache definitivo.
    """
    if not _tem_tesseract() or not stickers:
        return ""

    config = (
        "--psm 7 "
        "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
    )
    leituras: list[str] = []
    try:
        import pytesseract
        for st in stickers[:max_amostras]:
            crop = _crop_clampado(
                imagem, st.qr_left, st.qr_top + st.qr_height + 1,
                st.qr_width, ALTURA_SELLER_PX,
            )
            # Upscale 8x e sharpen agressivo (texto pequeno demais)
            w, h = crop.size
            pre = crop.convert("L").resize((w * 8, h * 8), Image.LANCZOS)
            pre = pre.filter(ImageFilter.UnsharpMask(radius=1.5, percent=200, threshold=1))
            pre = ImageOps.autocontrast(pre, cutoff=2)
            for lang in ("eng", "por"):
                t = pytesseract.image_to_string(pre, lang=lang, config=config).strip()
                if t:
                    leituras.append(_isolar_seller_sku(t))
    except Exception as exc:  # noqa: BLE001
        log.warning("Falha OCR Seller SKU: %s", exc)
        return ""

    if not leituras:
        return ""
    max_len = max(len(s) for s in leituras)
    if max_len == 0:
        return ""
    voto: list[str] = []
    for i in range(max_len):
        chars = [s[i] for s in leituras if i < len(s)]
        if not chars:
            break
        voto.append(Counter(chars).most_common(1)[0][0])
    return "".join(voto).strip("-:")
