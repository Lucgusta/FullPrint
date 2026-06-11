"""Agrupa etiquetas por SKU, preservando ordem de chegada.

Cada EtiquetaZPL representa 1 sticker individual (1 QR no GRF).
A contagem `qtd` no GrupoSKU eh igual ao numero de stickers.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from .parser import EtiquetaZPL


@dataclass
class GrupoSKU:
    sku: str
    descricao: str
    seller_sku: str = ""
    etiquetas: list[str] = field(default_factory=list)

    @property
    def qtd(self) -> int:
        """Numero de stickers do grupo."""
        return len(self.etiquetas)

    @property
    def total_stickers(self) -> int:
        # Mantido por compatibilidade com codigo antigo.
        return self.qtd


class EtiquetaAgrupador:
    def agrupar_por_sku(self, etiquetas: list[EtiquetaZPL]) -> "OrderedDict[str, GrupoSKU]":
        grupos: "OrderedDict[str, GrupoSKU]" = OrderedDict()
        for et in etiquetas:
            grupo = grupos.get(et.sku)
            if grupo is None:
                grupo = GrupoSKU(
                    sku=et.sku,
                    descricao=et.descricao,
                    seller_sku=et.seller_sku,
                )
                grupos[et.sku] = grupo
            grupo.etiquetas.append(et.zpl_raw)
            if not grupo.descricao and et.descricao:
                grupo.descricao = et.descricao
            if not grupo.seller_sku and et.seller_sku:
                grupo.seller_sku = et.seller_sku
        return grupos

    def resumo(self, grupos: "OrderedDict[str, GrupoSKU]") -> list[tuple[str, str, int]]:
        return [(g.sku, g.descricao, g.qtd) for g in grupos.values()]
