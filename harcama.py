#!/usr/bin/env python3
import argparse
import csv
import io
import json
from datetime import datetime, timedelta
from pathlib import Path

DATA = Path(__file__).parent / "harcamalar.json"
DEFAULT = {"ayarlar": {"butce": 0, "dil": "tr", "karanlik": False}, "tekrarlayan": [], "favoriler": [], "kayitlar": []}


def _bos_veri():
    return json.loads(json.dumps(DEFAULT))


def yukle_veri():
    if not DATA.exists():
        return _bos_veri()
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        veri = _bos_veri()
        veri["kayitlar"] = raw
        for k in veri["kayitlar"]:
            k.setdefault("kategori", "diger")
            k.setdefault("not", "")
            k.setdefault("tip", "gider")
        kaydet_veri(veri)
        return veri
    raw.setdefault("ayarlar", DEFAULT["ayarlar"].copy())
    raw.setdefault("tekrarlayan", [])
    raw.setdefault("favoriler", [])
    raw.setdefault("kayitlar", [])
    return raw


def kaydet_veri(veri):
    DATA.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def yukle():
    return yukle_veri()["kayitlar"]


def sonraki_id(kayitlar):
    return max((k["id"] for k in kayitlar), default=0) + 1


def simdi():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def ekle(aciklama, tutar, kategori="diger", note="", tip="gider", tekrar_id=None):
    veri = yukle_veri()
    kayit = {
        "id": sonraki_id(veri["kayitlar"]),
        "tarih": simdi(),
        "aciklama": aciklama.strip(),
        "tutar": round(float(tutar), 2),
        "kategori": kategori,
        "not": note.strip(),
        "tip": tip if tip in ("gider", "gelir") else "gider",
    }
    if tekrar_id is not None:
        kayit["tekrar_id"] = tekrar_id
    veri["kayitlar"].append(kayit)
    kaydet_veri(veri)
    return kayit


def guncelle(kayit_id, aciklama, tutar, kategori, note="", tip="gider"):
    veri = yukle_veri()
    for k in veri["kayitlar"]:
        if k["id"] == kayit_id:
            k["aciklama"] = aciklama.strip()
            k["tutar"] = round(float(tutar), 2)
            k["kategori"] = kategori
            k["not"] = note.strip()
            k["tip"] = tip if tip in ("gider", "gelir") else "gider"
            kaydet_veri(veri)
            return k
    return None


def get_kayit(kayit_id):
    for k in yukle():
        if k["id"] == kayit_id:
            return k
    return None


def sil(kayit_id):
    veri = yukle_veri()
    yeni = [k for k in veri["kayitlar"] if k["id"] != kayit_id]
    if len(yeni) == len(veri["kayitlar"]):
        return False
    veri["kayitlar"] = yeni
    kaydet_veri(veri)
    return True


def ayar_get(key, default=None):
    return yukle_veri()["ayarlar"].get(key, default)


def ayar_set(key, value):
    veri = yukle_veri()
    veri["ayarlar"][key] = value
    kaydet_veri(veri)


def _tarih(k):
    try:
        return datetime.strptime(k["tarih"], "%Y-%m-%d %H:%M")
    except ValueError:
        return datetime.min


def filtrele(kayitlar, q="", kategori="", tip="", ay="", yil=""):
    sonuc = kayitlar
    if q:
        q = q.lower()
        sonuc = [
            k for k in sonuc
            if q in k["aciklama"].lower() or q in k.get("not", "").lower()
        ]
    if kategori:
        sonuc = [k for k in sonuc if k.get("kategori") == kategori]
    if tip:
        sonuc = [k for k in sonuc if k.get("tip", "gider") == tip]
    if ay and yil:
        prefix = f"{yil}-{int(ay):02d}"
        sonuc = [k for k in sonuc if k["tarih"].startswith(prefix)]
    elif yil:
        sonuc = [k for k in sonuc if k["tarih"].startswith(str(yil))]
    return sonuc


def sirala(kayitlar, mode="date_desc"):
    key_fn = {
        "date_desc": lambda k: _tarih(k),
        "date_asc": lambda k: _tarih(k),
        "amount_desc": lambda k: k["tutar"],
        "amount_asc": lambda k: k["tutar"],
    }.get(mode, lambda k: _tarih(k))
    rev = mode in ("date_desc", "amount_desc")
    return sorted(kayitlar, key=key_fn, reverse=rev)


def donem_toplam(kayitlar, baslangic, bitis):
    gider = gelir = 0.0
    for k in kayitlar:
        t = _tarih(k)
        if baslangic <= t <= bitis:
            if k.get("tip", "gider") == "gelir":
                gelir += k["tutar"]
            else:
                gider += k["tutar"]
    return gider, gelir


def ay_toplam(kayitlar=None, yil=None, ay=None):
    now = datetime.now()
    yil = yil or now.year
    ay = ay or now.month
    bas = datetime(yil, ay, 1)
    bit = datetime(yil + 1, 1, 1) - timedelta(seconds=1) if ay == 12 else datetime(yil, ay + 1, 1) - timedelta(seconds=1)
    return donem_toplam(kayitlar or yukle(), bas, bit)


def hafta_toplam(kayitlar=None):
    now = datetime.now()
    bas = now - timedelta(days=now.weekday())
    bas = bas.replace(hour=0, minute=0, second=0, microsecond=0)
    bit = bas + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return donem_toplam(kayitlar or yukle(), bas, bit)


def yil_toplam(kayitlar=None, yil=None):
    yil = yil or datetime.now().year
    return donem_toplam(kayitlar or yukle(), datetime(yil, 1, 1), datetime(yil, 12, 31, 23, 59, 59))


def kategori_dagilimi(kayitlar=None, yil=None, ay=None):
    gider, _ = ay_toplam(kayitlar, yil, ay) if ay else (0, 0)
    kayitlar = kayitlar or yukle()
    now = datetime.now()
    yil, ay = yil or now.year, ay or now.month
    prefix = f"{yil}-{ay:02d}"
    dag = {}
    for k in kayitlar:
        if k.get("tip", "gider") != "gider":
            continue
        if not k["tarih"].startswith(prefix):
            continue
        cat = k.get("kategori", "diger")
        dag[cat] = dag.get(cat, 0) + k["tutar"]
    return dag


def aylik_trend(ay_sayisi=6):
    now = datetime.now()
    sonuc = []
    yil, ay = now.year, now.month
    for _ in range(ay_sayisi):
        g, gi = ay_toplam(yukle(), yil, ay)
        sonuc.append({"yil": yil, "ay": ay, "gider": g, "gelir": gi})
        ay -= 1
        if ay == 0:
            ay, yil = 12, yil - 1
    sonuc.reverse()
    return sonuc


def favori_listesi():
    return yukle_veri().get("favoriler", [])


def favori_ekle(aciklama, tutar, kategori="diger", tip="gider"):
    veri = yukle_veri()
    veri.setdefault("favoriler", [])
    item = {
        "id": sonraki_id(veri["favoriler"]),
        "aciklama": aciklama.strip(),
        "tutar": round(float(tutar), 2),
        "kategori": kategori,
        "tip": tip,
    }
    veri["favoriler"].append(item)
    kaydet_veri(veri)
    return item


def favori_sil(fav_id):
    veri = yukle_veri()
    yeni = [f for f in veri.get("favoriler", []) if f["id"] != fav_id]
    if len(yeni) == len(veri.get("favoriler", [])):
        return False
    veri["favoriler"] = yeni
    kaydet_veri(veri)
    return True


def hizli_ekle_listesi(limit=5):
    seen = {}
    for k in reversed(yukle()):
        key = (k["aciklama"], k.get("kategori", "diger"), k.get("tip", "gider"))
        if key not in seen:
            seen[key] = k["tutar"]
        if len(seen) >= limit:
            break
    return [{"aciklama": a, "tutar": t, "kategori": c, "tip": tip} for (a, c, tip), t in seen.items()]


def tekrarlayan_ekle(aciklama, tutar, kategori="diger", tip="gider", gun=1):
    veri = yukle_veri()
    item = {
        "id": sonraki_id(veri["tekrarlayan"]),
        "aciklama": aciklama.strip(),
        "tutar": round(float(tutar), 2),
        "kategori": kategori,
        "tip": tip,
        "gun": max(1, min(28, int(gun))),
    }
    veri["tekrarlayan"].append(item)
    kaydet_veri(veri)
    return item


def tekrarlayan_sil(item_id):
    veri = yukle_veri()
    yeni = [t for t in veri["tekrarlayan"] if t["id"] != item_id]
    if len(yeni) == len(veri["tekrarlayan"]):
        return False
    veri["tekrarlayan"] = yeni
    kaydet_veri(veri)
    return True


def tekrarlayan_uygula():
    veri = yukle_veri()
    now = datetime.now()
    ay_key = now.strftime("%Y-%m")
    for t in veri["tekrarlayan"]:
        if now.day < t.get("gun", 1):
            continue
        var = any(
            k.get("tekrar_id") == t["id"] and k["tarih"].startswith(ay_key)
            for k in veri["kayitlar"]
        )
        if var:
            continue
        ekle(t["aciklama"], t["tutar"], t["kategori"], tip=t["tip"], tekrar_id=t["id"])


def csv_icerik(kayitlar=None):
    kayitlar = kayitlar or yukle()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "tarih", "aciklama", "tutar", "kategori", "not", "tip"])
    for k in kayitlar:
        w.writerow([
            k["id"], k["tarih"], k["aciklama"], k["tutar"],
            k.get("kategori", ""), k.get("not", ""), k.get("tip", "gider"),
        ])
    return buf.getvalue()


def yedek_yukle(raw):
    if isinstance(raw, list):
        veri = _bos_veri()
        veri["kayitlar"] = raw
    else:
        veri = raw
    veri.setdefault("ayarlar", DEFAULT["ayarlar"].copy())
    veri.setdefault("tekrarlayan", [])
    veri.setdefault("favoriler", [])
    veri.setdefault("kayitlar", [])
    kaydet_veri(veri)


def toplam_deger():
    return sum(k["tutar"] for k in yukle() if k.get("tip", "gider") == "gider")


def liste():
    kayitlar = yukle()
    if not kayitlar:
        print("Kayıt yok.")
        return
    for k in kayitlar:
        print(f"{k['id']:>3} | {k['tarih']} | {k['aciklama']} | {k['tutar']:.2f} TL")


def toplam():
    kayitlar = yukle()
    g, gi = ay_toplam(kayitlar)
    print(f"Bu ay gider: {g:.2f} TL | gelir: {gi:.2f} TL ({len(kayitlar)} kayıt)")


def main():
    p = argparse.ArgumentParser(description="Harcama notu")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("ekle")
    e.add_argument("aciklama", nargs="+")
    e.add_argument("tutar", type=float)
    sub.add_parser("liste")
    sub.add_parser("toplam")
    s = sub.add_parser("sil")
    s.add_argument("id", type=int)
    args = p.parse_args()
    if args.cmd == "ekle":
        ekle(" ".join(args.aciklama), args.tutar)
        print("Eklendi.")
    elif args.cmd == "liste":
        liste()
    elif args.cmd == "toplam":
        toplam()
    elif args.cmd == "sil":
        print("Silindi." if sil(args.id) else "Bulunamadı.")


if __name__ == "__main__":
    main()
