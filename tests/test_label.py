"""Testes do modelo de etiqueta configuravel e do renderizador composto."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from src.core import label_renderer as R  # noqa: E402
from src.core.grf_decoder import StickerInfo  # noqa: E402
from src.core.label_models import (  # noqa: E402
    LabelModel,
    LabelModelStore,
    mm_para_dots,
)
from src.core.parser import EtiquetaZPL  # noqa: E402


class TestLabelModel(unittest.TestCase):
    def test_geometria_em_dots(self):
        m = LabelModel(
            id="x", nome="x", largura_mm=50, altura_mm=25, colunas=2,
            margem_esq_mm=1, margem_dir_mm=1, gap_colunas_mm=3, dpi=203,
        )
        self.assertEqual(m.altura_dots, mm_para_dots(25))          # 200
        self.assertEqual(m.largura_dots, mm_para_dots(50))         # 400
        self.assertEqual(m.x0_coluna(0), mm_para_dots(1))          # 8
        self.assertEqual(m.x0_coluna(1), 8 + 400 + mm_para_dots(3))  # 432
        self.assertEqual(m.linha_largura_dots % 8, 0)              # multiplo de 8 p/ ^GFA


class TestLabelModelStore(unittest.TestCase):
    def test_seed_e_persistencia(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "label_models.json"
            store = LabelModelStore(path)
            self.assertTrue(path.exists())  # seed gravado
            self.assertIsNotNone(store.get("shopee_10x15"))
            self.assertEqual(store.ativo().modo, "composto")  # 50x25 ativo por padrao

            # Recarrega de disco e mantem estado
            store.set_ativo("shopee_10x15")
            store2 = LabelModelStore(path)
            self.assertEqual(store2.ativo().id, "shopee_10x15")

    def test_pass_through_nao_removivel(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LabelModelStore(Path(tmp) / "m.json")
            self.assertFalse(store.remover("shopee_10x15"))


def _decodificar_gfa(gfa: str) -> tuple[Image.Image, int]:
    """Inverte imagem_para_gfa: ^GFA,total,total,rowbytes,HEX -> imagem 1-bit."""
    _total, _total2, rowbytes, hexstr = gfa[len("^GFA,"):].split(",", 3)
    rowbytes = int(rowbytes)
    invertido = bytes.fromhex(hexstr)
    raw = bytes(b ^ 0xFF for b in invertido)  # desfaz a inversao
    w = rowbytes * 8
    h = len(raw) // rowbytes
    return Image.frombytes("1", (w, h), raw), rowbytes


class TestGFA(unittest.TestCase):
    def test_round_trip(self):
        # Imagem com largura multipla de 8 (round-trip exato).
        img = Image.new("1", (24, 10), 1)
        for x in range(0, 24, 2):
            img.putpixel((x, 5), 0)  # alguns pixels pretos
        gfa = R.imagem_para_gfa(img)
        self.assertTrue(gfa.startswith("^GFA,"))
        recuperada, rowbytes = _decodificar_gfa(gfa)
        self.assertEqual(rowbytes, 3)  # 24/8
        self.assertEqual(recuperada.size, img.size)
        # tobytes() normaliza a representacao (1 vs 255) -> compara os bits.
        self.assertEqual(recuperada.tobytes(), img.tobytes())


def _etiqueta_sintetica(sku: str, com_qr: bool = True) -> EtiquetaZPL:
    folha = Image.new("1", (816, 1218), 1)
    md: dict = {"imagem_folha": folha, "grf_indice": 1}
    if com_qr:
        md["sticker"] = StickerInfo(sku=sku, qr_left=180, qr_top=24, qr_width=172, qr_height=172)
    return EtiquetaZPL(sku=sku, zpl_raw="", indice=1, metadados=md)


class TestGerarZpl(unittest.TestCase):
    def setUp(self):
        self.model = LabelModel(id="x", nome="x", colunas=2)

    def test_agrupa_em_linhas_de_2(self):
        etiquetas = [_etiqueta_sintetica(f"SKU{i}") for i in range(5)]  # 5 stickers
        zpl, n, ign = R.gerar_zpl_de_etiquetas(etiquetas, self.model, "T")
        self.assertEqual(n, 5)
        self.assertEqual(ign, 0)
        self.assertEqual(zpl.count("^XA"), 3)   # ceil(5/2) linhas
        self.assertIn("^GFA,", zpl)
        self.assertIn(f"^PW{self.model.linha_largura_dots}", zpl)

    def test_ignora_sem_qr(self):
        etiquetas = [_etiqueta_sintetica("A"), _etiqueta_sintetica("SEM-QR", com_qr=False)]
        zpl, n, ign = R.gerar_zpl_de_etiquetas(etiquetas, self.model, "T")
        self.assertEqual(n, 1)
        self.assertEqual(ign, 1)
        self.assertEqual(zpl.count("^XA"), 1)

    def test_preview_etiqueta_dimensao(self):
        et = _etiqueta_sintetica("A")
        img = R.preview_etiqueta(et, self.model)
        self.assertEqual(img.size, (self.model.largura_dots, self.model.altura_dots))


if __name__ == "__main__":
    unittest.main()
