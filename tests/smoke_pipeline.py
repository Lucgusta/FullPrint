"""Smoke test: pipeline completo parse -> agrupar -> gerar -> imprimir (DEV)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config.settings import load_settings  # noqa: E402
from src.core.agrupador import EtiquetaAgrupador  # noqa: E402
from src.core.gerador import GeradorLoteZPL  # noqa: E402
from src.core.parser import ShopeeZPLParser  # noqa: E402
from src.services.printer import ZebraPrinterService  # noqa: E402


def main() -> int:
    settings = load_settings()
    txt = ROOT / "data" / "exemplo_shopee.txt"
    if not txt.exists():
        print(f"FALHA: arquivo de exemplo nao encontrado em {txt}")
        return 1

    parser = ShopeeZPLParser(encoding_primario=settings.printer_encoding)
    etiquetas = parser.parse_file(txt)
    print(f"[parse] {len(etiquetas)} etiquetas extraidas")
    for e in etiquetas:
        print(f"  - idx={e.indice:02d} sku={e.sku} desc={e.descricao[:40]!r}")

    agrupador = EtiquetaAgrupador()
    grupos = agrupador.agrupar_por_sku(etiquetas)
    print(f"[agrupar] {len(grupos)} grupos:")
    for sku, desc, qtd in agrupador.resumo(grupos):
        print(f"  - {sku} ({qtd}x) {desc[:40]!r}")

    gerador = GeradorLoteZPL(templates_dir=settings.templates_dir)
    zpl_final = gerador.gerar_zpl_final(grupos, lote_id="SMOKE")
    n_blocos = zpl_final.count("^XA")
    print(f"[gerar] {len(zpl_final)} bytes, {n_blocos} blocos ^XA (esperado: {len(grupos) + len(etiquetas)})")

    printer = ZebraPrinterService(
        encoding=settings.printer_encoding,
        dev_mode=True,
        dev_output_dir=settings.printer_dev_output_dir,
    )
    printer.print_zpl(zpl_final, printer_name="[DEV]", job_name="SMOKE-TEST")

    saidas = sorted(settings.printer_dev_output_dir.glob("*SMOKE*.zpl"))
    if not saidas:
        print("FALHA: nenhum arquivo gerado em data/dev_output/")
        return 2
    print(f"[print] OK -> {saidas[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
