"""Parser ZPL para arquivos Shopee.

Define a interface abstrata `MarketplaceParser` (Strategy Pattern) e a
implementação concreta `ShopeeZPLParser`. Novos marketplaces (Mercado Livre,
etc.) implementam a mesma interface na Fase 2.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..utils import zpl_utils
from ..utils.logger import get_logger
from . import grf_decoder, ocr_descricao
from .sku_catalog import SKUCatalog

log = get_logger("parser")

ProgressCallback = Callable[[str], None]


@dataclass
class EtiquetaZPL:
    """Uma "etiqueta logica" — para GRF, equivale a 1 sticker (1 QR).

    Multiplos stickers do mesmo GRF compartilham `zpl_raw` e `grf_indice`
    via metadados, e o gerador deduplicará no momento de imprimir.
    """
    sku: str                       # SKU numerico do Shopee (sempre vem do QR)
    descricao: str
    zpl_raw: str
    indice: int = 0                # indice global do sticker
    seller_sku: str = ""           # opcional, vem do cache manual
    metadados: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sku": self.sku,
            "desc": self.descricao,
            "zpl_raw": self.zpl_raw,
            "indice": self.indice,
            "seller_sku": self.seller_sku,
            "metadados": dict(self.metadados),
        }


class MarketplaceParser(ABC):
    """Interface base para parsers de marketplaces."""

    nome: str = "abstrato"

    @abstractmethod
    def parse_file(self, filepath: str | Path) -> list[EtiquetaZPL]:
        ...

    @abstractmethod
    def parse_content(self, conteudo: str) -> list[EtiquetaZPL]:
        ...


class ShopeeZPLParser(MarketplaceParser):
    nome = "Shopee"

    def __init__(
        self,
        encoding_primario: str = "utf-8",
        progress_callback: ProgressCallback | None = None,
        catalog: SKUCatalog | None = None,
    ) -> None:
        self.encoding_primario = encoding_primario
        self.progress_callback = progress_callback or (lambda _msg: None)
        self.catalog = catalog

    def parse_file(self, filepath: str | Path) -> list[EtiquetaZPL]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

        conteudo = self._ler_com_fallback(path)
        etiquetas = self.parse_content(conteudo)
        log.info("Parse concluido: %s -> %d etiquetas", path.name, len(etiquetas))
        return etiquetas

    def parse_content(self, conteudo: str) -> list[EtiquetaZPL]:
        # Auto-detect: arquivos da Shopee Full em GRF (imagem rasterizada)
        # nao tem ^FD legivel; precisam de QR+OCR para extrair SKU/descricao.
        if grf_decoder.has_grf_z64(conteudo):
            return self._parse_grf(conteudo)
        return self._parse_texto(conteudo)

    def _parse_texto(self, conteudo: str) -> list[EtiquetaZPL]:
        blocos = zpl_utils.extrair_blocos(conteudo)
        etiquetas: list[EtiquetaZPL] = []
        for idx, bloco in enumerate(blocos, start=1):
            sku = zpl_utils.extrair_sku(bloco) or f"SEM-SKU-{idx:04d}"
            descricao = zpl_utils.extrair_descricao(bloco, sku)
            etiquetas.append(
                EtiquetaZPL(
                    sku=sku,
                    descricao=zpl_utils.sanitizar_para_zpl(descricao),
                    zpl_raw=bloco,
                    indice=idx,
                )
            )
        return etiquetas

    def _parse_grf(self, conteudo: str) -> list[EtiquetaZPL]:
        self.progress_callback("Decodificando etiquetas GRF...")
        grfs = grf_decoder.extrair_etiquetas(conteudo)
        if not grfs:
            return []

        # Para o Seller SKU OCR (multi-voto), reunimos TODAS as ocorrencias do
        # mesmo SKU em todos os GRFs — quanto mais amostras, melhor o voto.
        amostras_por_sku: dict[str, list[tuple[grf_decoder.EtiquetaGRF, grf_decoder.StickerInfo]]] = {}
        for g in grfs:
            for st in g.stickers:
                amostras_por_sku.setdefault(st.sku, []).append((g, st))

        self.progress_callback(f"OCR em {len(amostras_por_sku)} SKUs unicos...")
        desc_cache: dict[str, str] = {}
        seller_ocr_cache: dict[str, str] = {}
        for i, (sku, refs) in enumerate(amostras_por_sku.items(), start=1):
            g0, st0 = refs[0]
            desc_cache[sku] = ocr_descricao.ocr_descricao_at(g0.imagem, st0)
            # Seller SKU via voto so se nao tiver cache manual (mais confiavel).
            if self.catalog and self.catalog.get(sku):
                seller_ocr_cache[sku] = ""
            else:
                # Pega todas as imagens+sticker para voto. Limite no proprio metodo.
                stickers_amostras = [st for _, st in refs]
                seller_ocr_cache[sku] = ocr_descricao.ocr_seller_sku_at(g0.imagem, stickers_amostras)
            if i % 5 == 0:
                self.progress_callback(f"OCR {i}/{len(amostras_por_sku)}...")

        # 1 EtiquetaZPL por STICKER. Stickers do mesmo GRF compartilham zpl_raw;
        # o gerador deduplica via metadados['grf_indice'].
        etiquetas: list[EtiquetaZPL] = []
        indice_global = 0
        for g in grfs:
            for st in g.stickers:
                indice_global += 1
                cache_manual = self.catalog.get(st.sku) if self.catalog else None
                seller_sku = cache_manual or seller_ocr_cache.get(st.sku, "")
                etiquetas.append(
                    EtiquetaZPL(
                        sku=st.sku,
                        descricao=zpl_utils.sanitizar_para_zpl(desc_cache.get(st.sku, "")),
                        zpl_raw=g.zpl_raw,
                        indice=indice_global,
                        seller_sku=seller_sku,
                        metadados={
                            "grf_indice": g.indice,
                            "qr_left": st.qr_left,
                            "qr_top": st.qr_top,
                            "seller_ocr": seller_ocr_cache.get(st.sku, ""),
                            "seller_manual": bool(cache_manual),
                        },
                    )
                )
        return etiquetas

    def _ler_com_fallback(self, path: Path) -> str:
        encodings = [self.encoding_primario, "utf-8", "cp1252", "latin-1"]
        ultimo_erro: Exception | None = None
        for enc in encodings:
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError as exc:
                ultimo_erro = exc
                log.debug("Falha ao decodificar com %s: %s", enc, exc)
        raise UnicodeDecodeError(
            self.encoding_primario,
            b"",
            0,
            1,
            f"Nao foi possivel decodificar {path.name} ({ultimo_erro})",
        )
