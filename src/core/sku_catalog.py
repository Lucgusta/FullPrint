"""Cache persistente: SKU numerico do Shopee -> Seller SKU legível.

O TXT da Shopee Full não contém o Seller SKU como texto extraível (só
rasterizado no bitmap), então o usuário mapeia manualmente pela UI
(duplo-clique). O mapeamento é incremental: cada SKU novo é digitado
uma vez e fica persistido para sempre.
"""
from __future__ import annotations

import json
from pathlib import Path
from threading import Lock

from ..utils.logger import get_logger

log = get_logger("sku_catalog")


class SKUCatalog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = Lock()
        self._mapeamento: dict[str, str] = {}
        self._carregar()

    def _carregar(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                dados = json.load(fh)
                if isinstance(dados, dict):
                    self._mapeamento = {str(k): str(v) for k, v in dados.items()}
                    log.info("Catalogo carregado: %d SKUs mapeados", len(self._mapeamento))
        except Exception as exc:  # noqa: BLE001
            log.warning("Falha ao ler catalogo %s: %s", self.path, exc)

    def _salvar(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self._mapeamento, fh, ensure_ascii=False, indent=2, sort_keys=True)
            tmp.replace(self.path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Falha ao salvar catalogo: %s", exc)

    def get(self, sku_numerico: str) -> str | None:
        with self._lock:
            v = self._mapeamento.get(sku_numerico)
            return v if v else None

    def set(self, sku_numerico: str, seller_sku: str) -> None:
        with self._lock:
            if seller_sku.strip():
                self._mapeamento[sku_numerico] = seller_sku.strip()
            else:
                self._mapeamento.pop(sku_numerico, None)
            self._salvar()

    def total(self) -> int:
        return len(self._mapeamento)
