"""Gera o ZPL final do lote: separador + etiquetas por SKU."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from ..utils.logger import get_logger
from ..utils.zpl_utils import sanitizar_para_zpl
from .agrupador import GrupoSKU
from .parser import EtiquetaZPL

log = get_logger("gerador")


class GeradorLoteZPL:
    def __init__(self, templates_dir: Path) -> None:
        self.templates_dir = Path(templates_dir)

    def _gerar_linha_2_colunas(self, esq: dict | None, dir_item: dict | None) -> str:
        partes = ["^XA", "^CI28"]
        offsets = [(8, esq), (432, dir_item)]
        y_offset = 24
        
        for x_offset, dado in offsets:
            if not dado:
                continue
            if dado["tipo"] == "produto":
                sku = sanitizar_para_zpl(dado["sku"])
                desc = sanitizar_para_zpl(dado["desc"])
                partes.append(f"^FO{x_offset},{y_offset}^BQN,2,4^FDQA,{sku}^FS")
                partes.append(f"^FO{x_offset+110},{y_offset+10}^A0N,25,25^FD{sku}^FS")
                partes.append(f"^FO{x_offset+110},{y_offset+40}^FB270,5,0,L,0^A0N,20,20^FD{desc}^FS")
            elif dado["tipo"] == "separador":
                sku = sanitizar_para_zpl(dado["sku"])
                desc = sanitizar_para_zpl(dado["desc"])
                qtd = dado["qtd"]
                partes.append(f"^FO{x_offset},{y_offset+10}^FB380,2,0,L,0^A0N,30,30^FD{qtd} Produtos^FS")
                partes.append(f"^FO{x_offset},{y_offset+70}^FB380,4,0,L,0^A0N,20,20^FD(Etiqueta de separacao) = {sku}, {desc}^FS")
                
        partes.append("^XZ")
        return "\n".join(partes)

    def gerar_zpl_final(
        self,
        grupos: "OrderedDict[str, GrupoSKU]",
        lote_id: str = "MVP",
    ) -> str:
        partes: list[str] = []
        for grupo in grupos.values():
            # Cria a etiqueta de separador na esquerda, vazio na direita
            separador = {"tipo": "separador", "qtd": grupo.qtd, "sku": grupo.sku, "desc": grupo.descricao}
            partes.append(self._gerar_linha_2_colunas(separador, None))
            
            # Adiciona as etiquetas de produto em pares
            produtos = [{"tipo": "produto", "sku": grupo.sku, "desc": grupo.descricao} for _ in range(grupo.qtd)]
            for i in range(0, len(produtos), 2):
                esq = produtos[i]
                dir_item = produtos[i+1] if i + 1 < len(produtos) else None
                partes.append(self._gerar_linha_2_colunas(esq, dir_item))
                
        zpl_final = "\n".join(partes)
        log.info(
            "Lote %s gerado: %d grupos, %d blocos impressao, %d stickers totais",
            lote_id,
            len(grupos),
            len(partes),
            sum(g.qtd for g in grupos.values()),
        )
        return zpl_final

    def gerar_zpl_ordem_original(
        self,
        etiquetas: list[EtiquetaZPL],
        lote_id: str = "MVP",
    ) -> str:
        """Gera as etiquetas na ordem original, agrupando em 2 colunas, mas sem separadores."""
        vistos: set[int | str] = set()
        unicas = []
        for e in etiquetas:
            chave = e.metadados.get("grf_indice", e.indice)
            if chave in vistos:
                continue
            vistos.add(chave)
            unicas.append(e)
            
        partes: list[str] = []
        produtos = [{"tipo": "produto", "sku": e.sku, "desc": e.descricao} for e in unicas]
        for i in range(0, len(produtos), 2):
            esq = produtos[i]
            dir_item = produtos[i+1] if i + 1 < len(produtos) else None
            partes.append(self._gerar_linha_2_colunas(esq, dir_item))
            
        zpl_final = "\n".join(partes)
        log.info(
            "Lote %s gerado (ordem original): %d blocos impressao, %d stickers totais",
            lote_id,
            len(partes),
            len(unicas),
        )
        return zpl_final
