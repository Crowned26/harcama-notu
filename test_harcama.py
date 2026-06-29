import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import storage as s


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        self.p1 = patch.object(s, "DB_PATH", self.db)
        self.p2 = patch.object(s, "JSON_PATH", Path(self.tmp.name) / "none.json")
        self.p1.start()
        self.p2.start()
        s.init_db()

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()
        self.tmp.cleanup()

    def test_ekle_sil(self):
        s.ekle("kahve", 45, "yemek")
        self.assertEqual(len(s.yukle()), 1)
        s.sil(1)
        self.assertEqual(len(s.yukle()), 0)

    def test_otomatik_kategori(self):
        self.assertEqual(s.otomatik_kategori("starbucks kahve"), "yemek")

    def test_gelir_gider(self):
        s.ekle("maas", 1000, tip="gelir")
        s.ekle("market", 100, tip="gider")
        g, gi = s.ay_toplam()
        self.assertEqual(gi, 1000)
        self.assertEqual(g, 100)

    def test_pin(self):
        s.pin_kur("1234")
        self.assertTrue(s.pin_var_mi())
        self.assertTrue(s.pin_dogru("1234"))
        self.assertFalse(s.pin_dogru("0000"))

    def test_borc(self):
        s.borc_ekle("Ali", 200)
        s.borc_ode(1, 50)
        b = s.borc_listesi()[0]
        self.assertEqual(b["odenen"], 50)

    def test_bugun(self):
        s.ekle("test", 10)
        g, _ = s.bugun_toplam()
        self.assertEqual(g, 10)

    def test_ekle_tarih(self):
        s.ekle("market", 99, "yemek", tarih="2024-03-15")
        k = s.yukle()[0]
        self.assertTrue(k["tarih"].startswith("2024-03-15"))

    def test_guncelle_tarih(self):
        s.ekle("test", 10)
        s.guncelle(1, tarih="2022-05-20 14:30")
        k = s.get_kayit(1)
        self.assertTrue(k["tarih"].startswith("2022-05-20"))


if __name__ == "__main__":
    unittest.main()
