"""Experimento: decodifica blocos ~DG Z64 da Shopee e gera PNGs para inspecao.

Uso:
    python tests/render_grf.py [arquivo.txt]

Sem argumento, usa o TXT em data/exemplo_shopee.txt; passando o caminho,
processa o arquivo escolhido. Salva no maximo 3 etiquetas em data/dev_output/.
"""
from __future__ import annotations

import base64
import re
import sys
import zlib
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "dev_output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_PNG = 3

PATTERN = re.compile(
    r"~DG[^,]+,(?P<total>\d+),(?P<row>\d+),:Z64:(?P<b64>[A-Za-z0-9+/=]+):(?P<crc>[0-9A-Fa-f]+)",
    re.DOTALL,
)


def render(path: Path) -> None:
    conteudo = path.read_text(encoding="utf-8")
    blocos = list(PATTERN.finditer(conteudo))
    print(f"[scan] {len(blocos)} blocos ~DG Z64 em {path.name}")
    if not blocos:
        return

    for idx, m in enumerate(blocos[:MAX_PNG], start=1):
        total = int(m["total"])
        row_bytes = int(m["row"])
        try:
            comprimido = base64.b64decode(m["b64"])
            grf = zlib.decompress(comprimido)
        except Exception as exc:  # noqa: BLE001
            print(f"  #{idx}: falha decodificar ({exc})")
            continue

        if len(grf) != total:
            print(f"  #{idx}: aviso tamanho {len(grf)} != {total}")

        width = row_bytes * 8
        height = len(grf) // row_bytes
        try:
            img = Image.frombytes("1", (width, height), grf)
            # GRF: bit 1 = tinta (preto). PIL "1" frombytes: bit 1 = branco. Inverter.
            img = img.point(lambda p: 0 if p > 0 else 255).convert("1")
        except Exception as exc:  # noqa: BLE001
            print(f"  #{idx}: falha render ({exc})")
            continue

        out = OUT_DIR / f"etiqueta_{idx:02d}.png"
        img.save(out)
        print(f"  #{idx}: {width}x{height} -> {out}")


def main() -> int:
    if len(sys.argv) > 1:
        alvo = Path(sys.argv[1]).expanduser()
    else:
        alvo = ROOT / "data" / "exemplo_shopee.txt"
    if not alvo.exists():
        print(f"FALHA: arquivo nao encontrado: {alvo}")
        return 1
    render(alvo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
