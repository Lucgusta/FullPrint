"""Smoke test: modo texto parse -> preview -> impressao pass-through (DEV)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.settings import load_settings  # noqa: E402
from src.core.agrupador import EtiquetaAgrupador  # noqa: E402
from src.core.parser import ShopeeZPLParser  # noqa: E402
from src.services.printer import ZebraPrinterService  # noqa: E402


def main() -> int:
    settings = load_settings()
    txt = ROOT / "data" / "exemplo_shopee.txt"
    if not txt.exists():
        print(f"FALHA: arquivo de exemplo nao encontrado em {txt}")
        return 1

    parser = ShopeeZPLParser(encoding_primario=settings.printer_encoding)
    dados = txt.read_bytes()
    etiquetas = parser.parse_bytes(dados)
    print(f"[parse] {len(etiquetas)} etiquetas extraidas")
    for e in etiquetas:
        print(f"  - idx={e.indice:02d} sku={e.sku}")

    agrupador = EtiquetaAgrupador()
    grupos = agrupador.agrupar_por_sku(etiquetas)
    print(f"[agrupar] {len(grupos)} grupos:")
    for sku, seller, qtd in agrupador.resumo(grupos):
        print(f"  - {sku} ({qtd}x) seller={seller or '?'}")

    # Impressao: pass-through dos bytes ORIGINAIS do arquivo.
    printer = ZebraPrinterService(
        encoding=settings.printer_encoding,
        dev_mode=True,
        dev_output_dir=settings.printer_dev_output_dir,
    )
    printer.print_zpl(dados, printer_name="[DEV]", job_name="SMOKE-TEST")

    saidas = sorted(settings.printer_dev_output_dir.glob("*SMOKE*.zpl"))
    if not saidas:
        print("FALHA: nenhum arquivo gerado em data/dev_output/")
        return 2
    saida = saidas[-1]
    if saida.read_bytes() != dados:
        print(f"FALHA: saida {saida} difere do arquivo fonte (pass-through quebrado)")
        return 3
    print(f"[print] OK -> {saida}")
    print(f"[byte-compare] OK: saida identica ao fonte ({len(dados)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
