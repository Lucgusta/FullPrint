"""Testes do renderizador local de ZPL (Node + zpl-renderer-js).

Os testes que dependem do Node sao pulados (skip) quando o renderer nao esta
disponivel (Node ausente ou ``renderer/node_modules`` nao instalado), para nao
quebrar o CI/maquinas sem o motor. A logica pura (deteccao/erros) e sempre
testada.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from src.core import zpl_renderer as Z  # noqa: E402

ZPL_OK = "^XA^FO50,50^ADN,36,20^FDFullPrint^FS^XZ"


class TestDisponibilidade(unittest.TestCase):
    def test_reason_consistente_com_available(self):
        # is_available() == (unavailable_reason() is None)
        self.assertEqual(Z.is_available(), Z.unavailable_reason() is None)

    def test_zpl_vazio_levanta_erro(self):
        # Independe do Node: o vazio e barrado antes do subprocess.
        if not Z.is_available():
            self.skipTest("renderer indisponivel; erro de Node mascararia o de vazio")
        with self.assertRaises(Z.RendererError):
            Z.render_zpl_to_png("   ")


@unittest.skipUnless(Z.is_available(), "Node/renderer indisponivel")
class TestRenderReal(unittest.TestCase):
    def test_render_para_png_bytes(self):
        png = Z.render_zpl_to_png(ZPL_OK, dpmm=8, width_mm=50, height_mm=25)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"), "saida nao e PNG")

    def test_render_para_imagem_dimensoes(self):
        # 50mm x 8 dpmm = 400 ; 25mm x 8 = 200
        img = Z.render_zpl_to_image(ZPL_OK, dpmm=8, width_mm=50, height_mm=25)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (400, 200))

    def test_zpl_invalido_levanta_renderer_error(self):
        with self.assertRaises(Z.RendererError):
            Z.render_zpl_to_png("isso nao e zpl valido", dpmm=8, width_mm=50, height_mm=25)


if __name__ == "__main__":
    unittest.main()
