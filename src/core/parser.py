"""Parser ZPL para arquivos Shopee.

Define a interface abstrata `MarketplaceParser` (Strategy Pattern) e a
implementação concreta `ShopeeZPLParser`. Novos marketplaces (Mercado Livre,
etc.) implementam a mesma interface na Fase 2.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from ..utils import zpl_utils
from ..utils.logger import get_logger

log = get_logger("parser")


@dataclass
class EtiquetaZPL:
    sku: str
    descricao: str
    zpl_raw: str
    indice: int = 0
    metadados: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sku": self.sku,
            "desc": self.descricao,
            "zpl_raw": self.zpl_raw,
            "indice": self.indice,
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

    def __init__(self, encoding_primario: str = "utf-8") -> None:
        self.encoding_primario = encoding_primario

    def parse_file(self, filepath: str | Path) -> list[EtiquetaZPL]:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo nao encontrado: {path}")

        conteudo = self._ler_com_fallback(path)
        etiquetas = self.parse_content(conteudo)
        log.info("Parse concluido: %s -> %d etiquetas", path.name, len(etiquetas))
        return etiquetas

    def parse_content(self, conteudo: str) -> list[EtiquetaZPL]:
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
