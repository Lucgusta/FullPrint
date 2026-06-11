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
        self._template_separador: str | None = None

    def _carregar_template_separador(self) -> str:
        if self._template_separador is None:
            arquivo = self.templates_dir / "separador.zpl"
            self._template_separador = arquivo.read_text(encoding="utf-8")
        return self._template_separador

    def gerar_separador(
        self, sku: str, descricao: str, qtd: int, lote_id: str = "MVP"
    ) -> str:
        template = self._carregar_template_separador()
        return template.format(
            sku=sanitizar_para_zpl(sku),
            descricao=sanitizar_para_zpl(descricao)[:60],
            qtd=qtd,
            lote_id=lote_id,
            data=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

    def gerar_zpl_final(
        self,
        grupos: "OrderedDict[str, GrupoSKU]",
        lote_id: str = "MVP",
    ) -> str:
        partes: list[str] = []
        for grupo in grupos.values():
            separador = self.gerar_separador(
                grupo.sku, grupo.descricao, grupo.total_stickers, lote_id
            )
            partes.append(separador)
            partes.extend(grupo.etiquetas)
        zpl_final = "\n".join(partes)
        log.info(
            "Lote %s gerado: %d grupos, %d blocos, %d stickers totais",
            lote_id,
            len(grupos),
            sum(g.qtd for g in grupos.values()),
            sum(g.total_stickers for g in grupos.values()),
        )
        return zpl_final

    def gerar_zpl_ordem_original(
        self,
        etiquetas: list[EtiquetaZPL],
        lote_id: str = "MVP",
    ) -> str:
        """Concatena na ordem original do arquivo, sem separadores nem agrupamento.

        Como 1 EtiquetaZPL = 1 sticker (1 QR) e multiplos sticker compartilham
        o mesmo GRF, dedupe-se pelo grf_indice para nao reimprimir N vezes.
        """
        vistos: set[int | str] = set()
        partes: list[str] = []
        for e in etiquetas:
            chave = e.metadados.get("grf_indice", e.indice)
            if chave in vistos:
                continue
            vistos.add(chave)
            partes.append(e.zpl_raw)
        zpl_final = "\n".join(partes)
        log.info(
            "Lote %s gerado (ordem original): %d GRFs, %d stickers totais",
            lote_id,
            len(partes),
            len(etiquetas),
        )
        return zpl_final
