"""
Tests de regresión de la memoria legal CR (stdlib unittest, sin dependencias).

Ejecutar:  python -m unittest discover -s tests -v
Los tests de índice se saltan solos si no existe legal.db.
"""
import sys
import pathlib
import sqlite3
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from legal_rag import sources, chunker, graph  # noqa: E402

DB = ROOT / "legal.db"


class TestClasificacion(unittest.TestCase):
    def test_conocidos(self):
        c = sources.classify("codigo-penal-2026")
        self.assertEqual(c["doc_type"], "ley")
        self.assertEqual(c["rama"], "Derecho Penal")
        self.assertTrue(c["is_law"])

    def test_temario_no_es_ley(self):
        c = sources.classify("temario-derecho-civil-2025")
        self.assertEqual(c["doc_type"], "temario")
        self.assertFalse(c["is_law"])

    def test_nombres_nuevos(self):
        casos = {
            "ley-general-de-la-administracion-publica": ("ley", "Derecho Administrativo"),
            "constitucion-politica": ("ley", "Derecho Constitucional"),
            "codigo-de-trabajo": ("ley", "Derecho Laboral"),
            "codigo-tributario": ("ley", "Derecho Tributario"),
            "codigo-de-comercio": ("ley", "Derecho Comercial"),
            "jurisprudencia-sala-constitucional": ("jurisprudencia", "Derecho Constitucional"),
            "manual-de-doctrina-civil": ("doctrina", "Derecho Civil"),
        }
        for slug, (t, rama) in casos.items():
            c = sources.classify(slug)
            self.assertEqual(c["doc_type"], t, slug)
            self.assertEqual(c["rama"], rama, slug)

    def test_jurisprudencia_es_ley(self):
        self.assertTrue(sources.classify("jurisprudencia-sala-primera")["is_law"])


class TestVigencia(unittest.TestCase):
    def test_derogado(self):
        self.assertFalse(chunker.es_vigente("DEROGADO.- (Derogado por el artículo 81 ...)"))
        self.assertFalse(chunker.es_vigente("(Derogado por la ley N° 9406 del 30 de noviembre de 2016)"))
        self.assertFalse(chunker.es_vigente("Derogada por Ley N° 7020."))

    def test_vigente(self):
        self.assertTrue(chunker.es_vigente(
            "Todo aquel que por dolo, falta, negligencia o imprudencia causa a otro un daño, "
            "está obligado a repararlo junto con los perjuicios."))

    def test_clausula_derogatoria_es_vigente(self):
        # Un artículo que DEROGA otras normas SIGUE siendo ley vigente.
        self.assertTrue(chunker.es_vigente("Deróguese la Ley N° 123 de 1990."))
        self.assertTrue(chunker.es_vigente("Quedan derogadas las disposiciones que se opongan a este Código."))


class TestConcordancias(unittest.TestCase):
    def test_referencia_interna(self):
        self.assertIn("1068", graph.refs_in("según el artículo 1068 no pueden ser compradores"))

    def test_referencia_externa_se_descarta(self):
        # "artículo 5 de la Ley N° 7020" apunta a OTRA ley -> no se enlaza
        self.assertNotIn("5", graph.refs_in("conforme al artículo 5 de la Ley N° 7020"))

    def test_lista_de_referencias(self):
        self.assertTrue({"5", "6", "7"}.issubset(graph.refs_in("los artículos 5, 6 y 7 establecen")))


class TestChunker(unittest.TestCase):
    def test_troceo_y_vigencia(self):
        md = ("---\ndoc_kind: codigo\nsource: \"x.pdf\"\n---\n\n"
              "## Artículo 1\n\nTexto vigente del artículo uno sobre obligaciones.\n\n"
              "## Artículo 2\n\n(Derogado por la ley N° 9 del 2020)\n")
        p = pathlib.Path(tempfile.mkdtemp()) / "codigo-civil-2026.md"
        p.write_text(md, encoding="utf-8")
        by_art = {c["article"]: c for c in chunker.chunk_file(p)}
        self.assertEqual(by_art["1"]["doc_type"], "ley")
        self.assertEqual(by_art["1"]["vigente"], 1)
        self.assertEqual(by_art["2"]["vigente"], 0)   # derogado


@unittest.skipUnless(DB.exists(), "requiere índice: python -m legal_rag.index")
class TestIndice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.con = sqlite3.connect(DB)

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def test_art_1045_vigente_y_fiel(self):
        row = self.con.execute(
            "SELECT text, vigente FROM chunks WHERE slug='codigo-civil-2026' AND article='1045'"
        ).fetchone()
        self.assertIsNotNone(row, "art 1045 debe existir")
        self.assertEqual(row[1], 1, "art 1045 es ley vigente")
        self.assertIn("repararlo", row[0])

    def test_art_42_civil_derogado(self):
        row = self.con.execute(
            "SELECT vigente FROM chunks WHERE slug='codigo-civil-2026' AND article='42'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 0, "art 42 Civil está derogado")

    def test_hay_muchos_derogados_marcados(self):
        n = self.con.execute(
            "SELECT count(*) FROM chunks WHERE doc_type='ley' AND vigente=0").fetchone()[0]
        self.assertGreater(n, 300, "deben detectarse ~430 artículos derogados")

    def test_solo_ley_y_temario_separados(self):
        tipos = {r[0] for r in self.con.execute("SELECT DISTINCT doc_type FROM chunks")}
        self.assertIn("ley", tipos)
        self.assertIn("temario", tipos)


if __name__ == "__main__":
    unittest.main(verbosity=2)
