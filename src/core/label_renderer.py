"""Re-monta etiquetas no layout da bobina do usuario (modo ``composto``).

Estrategia: compor cada LINHA da bobina (todas as colunas) como UM bitmap, do
tamanho exato da midia, e enviar 1 bloco ZPL (``^GFA``) por linha. Assim cada
``^XA`` tem a altura de uma etiqueta -> a impressora sincroniza no gap a cada
linha (imprime todas) e o conteudo cai alinhado a etiqueta.

Os pixels do QR e do texto vem RECORTADOS do bitmap original da Shopee
(``grf_decoder.crop_qr`` / ``crop_texto``) — sem OCR, fidelidade de pixel. O
mesmo compositor gera a imagem do preview, entao o que se ve na tela e
exatamente o que sai no papel.
"""
from __future__ import annotations

from PIL import Image, ImageOps

from ..utils.logger import get_logger
from . import grf_decoder
from .label_models import LabelModel

log = get_logger("label_renderer")

# Espacamentos internos da etiqueta (dots). Pequenos e fixos: o que importa
# para o alinhamento na bobina sao as margens/vaos do modelo (configuraveis).
PAD = 4
GAP_QR_TEXTO = 8


def _trim_tinta(img: Image.Image) -> Image.Image:
    """Apara o espaco branco em volta da tinta (bbox dos pixels pretos)."""
    cinza = img.convert("L")
    bbox = ImageOps.invert(cinza).getbbox()  # bbox dos pixels nao-brancos
    return img.crop(bbox) if bbox else img


def _resize_fit(img: Image.Image, box_w: int, box_h: int, max_escala: float = 3.0) -> Image.Image:
    """Redimensiona preservando proporcao para caber em (box_w, box_h)."""
    w, h = img.size
    if w == 0 or h == 0:
        return img
    escala = min(box_w / w, box_h / h, max_escala)
    novo = (max(1, round(w * escala)), max(1, round(h * escala)))
    return img.convert("L").resize(novo, Image.LANCZOS).convert("1")


def _colocar_etiqueta(
    canvas: Image.Image,
    x0: int,
    qr_img: Image.Image,
    texto_img: Image.Image | None,
    model: LabelModel,
) -> None:
    """Compoe UMA etiqueta (QR a esquerda, texto a direita) sobre o canvas."""
    altura = model.altura_dots
    topo = model.dots(model.margem_topo_mm)
    qr_dots = min(model.dots(model.qr_mm), altura - topo - 2 * PAD)
    qr = qr_img.convert("L").resize((qr_dots, qr_dots), Image.NEAREST).convert("1")
    qr_y = topo + max(0, (altura - topo - qr_dots) // 2)
    canvas.paste(qr, (x0 + PAD, qr_y))

    if texto_img is None:
        return
    texto = _trim_tinta(texto_img)
    box_x = x0 + PAD + qr_dots + GAP_QR_TEXTO
    box_w = model.largura_dots - PAD - qr_dots - GAP_QR_TEXTO - PAD
    box_y = topo + PAD
    box_h = altura - topo - 2 * PAD
    if box_w <= 0 or box_h <= 0:
        return
    txt = _resize_fit(texto, box_w, box_h)
    txt_y = box_y + max(0, (box_h - txt.size[1]) // 2)
    canvas.paste(txt, (box_x, txt_y))


def compor_etiqueta(qr_img: Image.Image, texto_img: Image.Image | None, model: LabelModel) -> Image.Image:
    """Imagem de UMA etiqueta isolada (para o preview)."""
    canvas = Image.new("1", (model.largura_dots, model.altura_dots), 1)
    _colocar_etiqueta(canvas, 0, qr_img, texto_img, model)
    return canvas


def compor_linha(itens: list[tuple[Image.Image, Image.Image | None]], model: LabelModel) -> Image.Image:
    """Imagem de UMA linha da bobina (ate ``model.colunas`` etiquetas)."""
    canvas = Image.new("1", (model.linha_largura_dots, model.altura_dots), 1)
    for col, (qr_img, texto_img) in enumerate(itens[: model.colunas]):
        _colocar_etiqueta(canvas, model.x0_coluna(col), qr_img, texto_img, model)
    return canvas


def imagem_para_gfa(img: Image.Image) -> str:
    """Serializa uma imagem 1-bit como campo grafico ZPL ``^GFA`` (hex ASCII).

    ZPL: bit 1 = tinta (preto). PIL "1".tobytes(): bit 1 = branco (255).
    Por isso invertemos os bytes. A largura deve ser multipla de 8 para os
    bits de padding nao virarem uma faixa preta na borda."""
    bw = img.convert("1")
    w, h = bw.size
    row_bytes = (w + 7) // 8
    raw = bw.tobytes()
    invertido = bytes(b ^ 0xFF for b in raw)
    total = len(invertido)
    return f"^GFA,{total},{total},{row_bytes},{invertido.hex().upper()}"


def gerar_zpl(linhas: list[Image.Image], model: LabelModel, lote_id: str = "LOTE") -> str:
    """Monta o ZPL final: 1 bloco ^XA por linha da bobina."""
    largura = model.linha_largura_dots
    altura = model.altura_dots
    blocos: list[str] = []
    for img in linhas:
        blocos.append(
            "^XA\n"
            "^CI28\n"
            "^LH0,0\n"
            f"^PW{largura}\n"
            f"^LL{altura}\n"
            f"^FO0,0{imagem_para_gfa(img)}^FS\n"
            "^PQ1,0,0,N\n"
            "^XZ"
        )
    log.info("Lote %s composto: %d linhas (%dx%d dots cada)", lote_id, len(linhas), largura, altura)
    return "\n".join(blocos)


def _qr_e_texto(etiqueta) -> tuple[Image.Image, Image.Image | None] | None:
    """Extrai (QR, texto) recortados do bitmap para uma EtiquetaZPL.

    Retorna None se a etiqueta nao tem sticker (ex.: placeholder SEM-QR),
    pois sem o QR nao da para compor a etiqueta nova.
    """
    folha = etiqueta.metadados.get("imagem_folha")
    st = etiqueta.metadados.get("sticker")
    if folha is None or st is None:
        return None
    return grf_decoder.crop_qr(folha, st), grf_decoder.crop_texto(folha, st)


def preview_etiqueta(etiqueta, model: LabelModel) -> Image.Image | None:
    """Imagem da etiqueta composta para UMA EtiquetaZPL (preview na UI)."""
    par = _qr_e_texto(etiqueta)
    if par is None:
        return None
    return compor_etiqueta(par[0], par[1], model)


def gerar_zpl_de_etiquetas(etiquetas: list, model: LabelModel, lote_id: str = "LOTE") -> tuple[str, int, int]:
    """Compoe o lote inteiro a partir das EtiquetaZPL parseadas.

    Agrupa em linhas de ``model.colunas`` na ordem do arquivo. Retorna
    (zpl, qtd_compostas, qtd_ignoradas) — ignoradas = stickers sem QR.
    """
    pares: list[tuple[Image.Image, Image.Image | None]] = []
    ignoradas = 0
    for et in etiquetas:
        par = _qr_e_texto(et)
        if par is None:
            ignoradas += 1
            continue
        pares.append(par)

    linhas: list[Image.Image] = []
    for i in range(0, len(pares), model.colunas):
        linhas.append(compor_linha(pares[i : i + model.colunas], model))
    return gerar_zpl(linhas, model, lote_id=lote_id), len(pares), ignoradas
