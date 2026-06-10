"""Agrupa etiquetas por SKU, preservando ordem de chegada."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from .parser import EtiquetaZPL


@dataclass
class GrupoSKU:
    sku: str
    descricao: str
    etiquetas: list[str] = field(default_factory=list)

    @property
    def qtd(self) -> int:
        return len(self.etiquetas)


class EtiquetaAgrupador:
    def agrupar_por_sku(self, etiquetas: list[EtiquetaZPL]) -> "OrderedDict[str, GrupoSKU]":
        grupos: "OrderedDict[str, GrupoSKU]" = OrderedDict()
        for et in etiquetas:
            grupo = grupos.get(et.sku)
            if grupo is None:
                grupo = GrupoSKU(sku=et.sku, descricao=et.descricao)
                grupos[et.sku] = grupo
            grupo.etiquetas.append(et.zpl_raw)
            if (not grupo.descricao or grupo.descricao == "Sem descricao") and et.descricao:
                grupo.descricao = et.descricao
        return grupos

    def resumo(self, grupos: "OrderedDict[str, GrupoSKU]") -> list[tuple[str, str, int]]:
        return [(g.sku, g.descricao, g.qtd) for g in grupos.values()]
