"""Smoke test: GRF (Shopee Full) parse -> preview -> impressao pass-through (DEV).

Uso:
    python tests/smoke_grf.py <arquivo.txt>

Sem argumento, tenta `data/exemplo_grf.txt`. Use o seu TXT real da Shopee Full.
Valida que o que vai para a "impressora" (dev_output) e IDENTICO byte a byte
ao arquivo fonte — a garantia central do pass-through.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.settings import load_settings  # noqa: E402
from src.core.agrupador import EtiquetaAgrupador  # noqa: E402
from src.core.grf_decoder import has_grf_z64  # noqa: E402
from src.core.parser import ShopeeZPLParser  # noqa: E402
from src.services.printer import ZebraPrinterService  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1:
        txt = Path(sys.argv[1]).expanduser()
    else:
        txt = ROOT / "data" / "exemplo_grf.txt"
    if not txt.exists():
        print(f"FALHA: arquivo nao encontrado: {txt}")
        print("Passe o caminho de um TXT real da Shopee Full como argumento.")
        return 1

    settings = load_settings()
    parser = ShopeeZPLParser(
        encoding_primario=settings.printer_encoding,
        progress_callback=lambda m: print(f"  [progress] {m}"),
    )

    dados = txt.read_bytes()
    conteudo = parser._decodificar_com_fallback(dados)
    print(f"[detect] has_grf_z64={has_grf_z64(conteudo)}")
    if not has_grf_z64(conteudo):
        print("FALHA: arquivo nao parece GRF (sem ~DG :Z64:)")
        return 2

    t0 = time.perf_counter()
    etiquetas = parser.parse_bytes(dados)
    dt = time.perf_counter() - t0
    print(f"[parse] {len(etiquetas)} stickers em {dt:.1f}s")

    grupos = EtiquetaAgrupador().agrupar_por_sku(etiquetas)
    print(f"[agrupar] {len(grupos)} SKUs:")
    for g in list(grupos.values())[:5]:
        seller = g.seller_sku or "?"
        print(f"  - {g.sku[:40]:40s} | seller={seller[:20]:20s} | {g.qtd} stickers")
    if len(grupos) > 5:
        print(f"  ... +{len(grupos)-5} SKUs")

    # Impressao: pass-through dos bytes ORIGINAIS do arquivo (sem re-render).
    printer = ZebraPrinterService(
        encoding=settings.printer_encoding,
        dev_mode=True,
        dev_output_dir=settings.printer_dev_output_dir,
    )
    printer.print_zpl(dados, printer_name="[DEV]", job_name="SMOKE-GRF")
    saidas = sorted(settings.printer_dev_output_dir.glob("*SMOKE_GRF*.zpl"))
    if not saidas:
        print("FALHA: nao gerou arquivo em data/dev_output/")
        return 3
    saida = saidas[-1]

    if saida.read_bytes() != dados:
        print(f"FALHA: saida {saida} difere do arquivo fonte (pass-through quebrado)")
        return 4
    print(f"[print] OK -> {saida}")
    print(f"[byte-compare] OK: saida identica ao fonte ({len(dados)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
