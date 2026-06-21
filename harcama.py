#!/usr/bin/env python3
"""CLI + storage re-export."""
import argparse
import storage as s

yukle = s.yukle
yukle_veri = s.export_veri
ekle = s.ekle
sil = s.sil
guncelle = lambda kid, aciklama, tutar, kategori, note="", tip="gider": s.guncelle(
    kid, aciklama=aciklama, tutar=tutar, kategori=kategori, not=note, tip=tip)
get_kayit = s.get_kayit
ayar_get = s.ayar_get
ayar_set = s.ayar_set
filtrele = s.filtrele
sirala = s.sirala
ay_toplam = s.ay_toplam
hafta_toplam = s.hafta_toplam
yil_toplam = s.yil_toplam
kategori_dagilimi = lambda kayitlar=None, yil=None, ay=None: s.kategori_dagilimi(yil or __import__("datetime").datetime.now().year, ay or __import__("datetime").datetime.now().month)
hizli_ekle_listesi = s.hizli_ekle_listesi
favori_listesi = s.favori_listesi
favori_ekle = s.favori_ekle
favori_sil = s.favori_sil
tekrarlayan_ekle = s.tekrarlayan_ekle
tekrarlayan_sil = s.tekrarlayan_sil
tekrarlayan_uygula = s.tekrarlayan_uygula
csv_icerik = s.csv_icerik
yedek_yukle = s.yedek_yukle
toplam_deger = lambda: sum(k["tutar"] for k in yukle() if k.get("tip") == "gider")


def liste():
    k = yukle()
    if not k:
        print("Kayıt yok.")
        return
    for x in k:
        print(f"{x['id']:>3} | {x['tarih']} | {x['aciklama']} | {x['tutar']:.2f} TL")


def toplam():
    g, gi = ay_toplam()
    print(f"Bu ay gider: {g:.2f} | gelir: {gi:.2f} TL")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("ekle")
    e.add_argument("aciklama", nargs="+")
    e.add_argument("tutar", type=float)
    sub.add_parser("liste")
    sub.add_parser("toplam")
    d = sub.add_parser("sil")
    d.add_argument("id", type=int)
    a = p.parse_args()
    if a.cmd == "ekle":
        ekle(" ".join(a.aciklama), a.tutar)
    elif a.cmd == "liste":
        liste()
    elif a.cmd == "toplam":
        toplam()
    elif a.cmd == "sil":
        sil(a.id)


if __name__ == "__main__":
    main()
