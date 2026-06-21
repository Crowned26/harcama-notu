import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import harcama as h


class TestHarcama(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "data.json"
        self.patcher = patch.object(h, "DATA", self.path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_ekle_ve_sil(self):
        h.ekle("kahve", 45, "yemek")
        self.assertEqual(len(h.yukle()), 1)
        self.assertTrue(h.sil(1))
        self.assertEqual(len(h.yukle()), 0)

    def test_id_cakismasi_yok(self):
        h.ekle("a", 10)
        h.ekle("b", 20)
        h.sil(1)
        h.ekle("c", 30)
        ids = [k["id"] for k in h.yukle()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_gelir_gider(self):
        h.ekle("maas", 1000, tip="gelir")
        h.ekle("market", 100, tip="gider")
        g, gi = h.ay_toplam()
        self.assertEqual(gi, 1000)
        self.assertEqual(g, 100)

    def test_filtre(self):
        h.ekle("kahve", 10, "yemek")
        h.ekle("otobus", 5, "ulasim")
        self.assertEqual(len(h.filtrele(h.yukle(), q="kah")), 1)

    def test_yedek(self):
        h.ekle("x", 1)
        raw = json.loads(self.path.read_text())
        h.yedek_yukle(raw)
        self.assertEqual(len(h.yukle()), 1)


if __name__ == "__main__":
    unittest.main()
