"""Smoke test: pipeline GRF (Shopee Full) parse -> OCR -> agrupa -> gera -> grava DEV.

Uso:
    python tests/smoke_grf.py <arquivo.txt>

Sem argumento, tenta `data/exemplo_grf.txt`. Use o seu TXT real da Shopee Full
para validar a integracao com QR + OCR antes de imprimir de verdade.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.settings import load_settings  # noqa: E402
from src.core.agrupador import EtiquetaAgrupador  # noqa: E402
from src.core.gerador import GeradorLoteZPL  # noqa: E402
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

    conteudo = parser._ler_com_fallback(txt)
    print(f"[detect] has_grf_z64={has_grf_z64(conteudo)}")
    if not has_grf_z64(conteudo):
        print("FALHA: arquivo nao parece GRF (sem ~DG :Z64:)")
        return 2

    t0 = time.perf_counter()
    etiquetas = parser.parse_content(conteudo)
    dt = time.perf_counter() - t0
    print(f"[parse] {len(etiquetas)} etiquetas em {dt:.1f}s")

    grupos = EtiquetaAgrupador().agrupar_por_sku(etiquetas)
    total_stickers = sum(g.total_stickers for g in grupos.values())
    print(f"[agrupar] {len(grupos)} SKUs / {total_stickers} stickers totais:")
    for g in list(grupos.values())[:5]:
        print(f"  - {g.sku[:32]:32s} | {g.descricao[:42]:42s} | {g.qtd}x = {g.total_stickers} stickers")
    if len(grupos) > 5:
        print(f"  ... +{len(grupos)-5} SKUs")

    gerador = GeradorLoteZPL(settings.templates_dir)
    # Caminho GRF: 1 EtiquetaZPL = 1 sticker; gerador deduplica pelo grf_indice
    # para nao reimprimir o GRF inteiro N vezes (cada GRF imprime N stickers automaticamente).
    zpl_final = gerador.gerar_zpl_ordem_original(etiquetas, lote_id="SMOKE-GRF")
    print(f"[gerar] {len(zpl_final)} bytes ({zpl_final.count('^XA')} blocos ^XA, {zpl_final.count('~DG')} GRFs)")

    printer = ZebraPrinterService(
        encoding=settings.printer_encoding,
        dev_mode=True,
        dev_output_dir=settings.printer_dev_output_dir,
    )
    printer.print_zpl(zpl_final, printer_name="[DEV]", job_name="SMOKE-GRF")
    saidas = sorted(settings.printer_dev_output_dir.glob("*SMOKE_GRF*.zpl"))
    if not saidas:
        print("FALHA: nao gerou arquivo em data/dev_output/")
        return 3
    print(f"[print] OK -> {saidas[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
