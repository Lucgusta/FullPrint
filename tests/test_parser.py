"""Testes essenciais do parser ZPL Shopee."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.agrupador import EtiquetaAgrupador  # noqa: E402
from src.core.gerador import GeradorLoteZPL  # noqa: E402
from src.core.parser import ShopeeZPLParser  # noqa: E402


CONTEUDO_EXEMPLO = """
^XA
^CI28
^FO50,50^A0N,40,40^FDSKU: ABC-123^FS
^FO50,120^A0N,30,30^FDCamiseta Algodao Azul M^FS
^BCN,80,Y,N,N^FDABC-123^FS
^XZ
^XA
^FO50,50^A0N,40,40^FDSKU: ABC-123^FS
^FO50,120^A0N,30,30^FDCamiseta Algodao Azul M^FS
^XZ
^XA
^FO50,50^A0N,40,40^FDSKU: XYZ-999^FS
^FO50,120^A0N,30,30^FDCalca Jeans Preta 42^FS
^XZ
""".strip()


class TestShopeeParser(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = ShopeeZPLParser()

    def test_extrai_tres_blocos(self):
        etiquetas = self.parser.parse_content(CONTEUDO_EXEMPLO)
        self.assertEqual(len(etiquetas), 3)

    def test_sku_extraido(self):
        etiquetas = self.parser.parse_content(CONTEUDO_EXEMPLO)
        self.assertEqual(etiquetas[0].sku, "ABC-123")
        self.assertEqual(etiquetas[2].sku, "XYZ-999")

    def test_descricao_extraida(self):
        etiquetas = self.parser.parse_content(CONTEUDO_EXEMPLO)
        self.assertIn("Camiseta", etiquetas[0].descricao)
        self.assertIn("Calca", etiquetas[2].descricao)

    def test_zpl_raw_preservado(self):
        etiquetas = self.parser.parse_content(CONTEUDO_EXEMPLO)
        for et in etiquetas:
            self.assertTrue(et.zpl_raw.startswith("^XA"))
            self.assertTrue(et.zpl_raw.endswith("^XZ"))


class TestAgrupador(unittest.TestCase):
    def test_agrupa_por_sku(self):
        parser = ShopeeZPLParser()
        agrupador = EtiquetaAgrupador()
        etiquetas = parser.parse_content(CONTEUDO_EXEMPLO)
        grupos = agrupador.agrupar_por_sku(etiquetas)
        self.assertEqual(len(grupos), 2)
        self.assertEqual(grupos["ABC-123"].qtd, 2)
        self.assertEqual(grupos["XYZ-999"].qtd, 1)


class TestGerador(unittest.TestCase):
    def test_lote_contem_separador_e_etiquetas(self):
        parser = ShopeeZPLParser()
        agrupador = EtiquetaAgrupador()
        gerador = GeradorLoteZPL(ROOT / "src" / "core" / "templates")
        etiquetas = parser.parse_content(CONTEUDO_EXEMPLO)
        grupos = agrupador.agrupar_por_sku(etiquetas)
        zpl_final = gerador.gerar_zpl_final(grupos, lote_id="TESTE")

        self.assertIn("--- SEPARACAO ---", zpl_final)
        self.assertIn("SKU: ABC-123", zpl_final)
        self.assertIn("SKU: XYZ-999", zpl_final)
        self.assertIn("QTD: 2 ETIQUETAS", zpl_final)
        self.assertIn("QTD: 1 ETIQUETAS", zpl_final)
        self.assertEqual(zpl_final.count("^XA"), 5)


if __name__ == "__main__":
    unittest.main()
