"""Gera o ZPL final do lote: separador + etiquetas por SKU."""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from ..utils.logger import get_logger
from ..utils.zpl_utils import sanitizar_para_zpl
from .agrupador import GrupoSKU

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
                grupo.sku, grupo.descricao, grupo.qtd, lote_id
            )
            partes.append(separador)
            partes.extend(grupo.etiquetas)
        zpl_final = "\n".join(partes)
        log.info(
            "Lote %s gerado: %d grupos, %d etiquetas",
            lote_id,
            len(grupos),
            sum(g.qtd for g in grupos.values()),
        )
        return zpl_final
