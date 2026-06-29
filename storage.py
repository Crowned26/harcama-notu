import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE / "data.db"))
JSON_PATH = BASE / "harcamalar.json"

KATEGORI_EMOJI = {
    "yemek": "🍔", "ulasim": "🚗", "eglence": "🎮", "konut": "🏠",
    "saglik": "💊", "diger": "📦",
}

AUTO_KAT = {
    "kahve": "yemek", "market": "yemek", "yemek": "yemek", "restoran": "yemek",
    "otobus": "ulasim", "metro": "ulasim", "benzin": "ulasim", "taksi": "ulasim",
    "netflix": "eglence", "sinema": "eglence", "oyun": "eglence",
    "kira": "konut", "elektrik": "konut", "su": "konut",
    "eczane": "saglik", "doktor": "saglik",
}


def _hash_pin(pin):
    return hashlib.sha256(pin.encode()).hexdigest()


@contextmanager
def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS kayitlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT NOT NULL,
            aciklama TEXT NOT NULL,
            tutar REAL NOT NULL,
            kategori TEXT DEFAULT 'diger',
            notes TEXT DEFAULT '',
            tip TEXT DEFAULT 'gider',
            odeme TEXT DEFAULT 'nakit',
            konum TEXT DEFAULT '',
            doviz TEXT DEFAULT 'TRY',
            doviz_tutar REAL,
            bolen INTEGER DEFAULT 1,
            taksit_toplam INTEGER,
            taksit_no INTEGER,
            tekrar_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS favoriler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aciklama TEXT, tutar REAL, kategori TEXT, tip TEXT, odeme TEXT DEFAULT 'nakit'
        );
        CREATE TABLE IF NOT EXISTS tekrarlayan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aciklama TEXT, tutar REAL, kategori TEXT, tip TEXT, gun INTEGER DEFAULT 1, odeme TEXT DEFAULT 'nakit'
        );
        CREATE TABLE IF NOT EXISTS borclar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kime TEXT, tutar REAL, odenen REAL DEFAULT 0, notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS kategori_limitleri (
            kategori TEXT PRIMARY KEY, max_tutar REAL
        );
        CREATE TABLE IF NOT EXISTS ozel_kategoriler (
            ad TEXT PRIMARY KEY, emoji TEXT DEFAULT '📌'
        );
        CREATE TABLE IF NOT EXISTS ayarlar (key TEXT PRIMARY KEY, value TEXT);
        """)
    _migrate_json()
    _defaults()


def _defaults():
    defaults = {
        "butce": "0", "hafta_butce": "0", "tasarruf_hedef": "0",
        "usd_kur": "34", "eur_kur": "37", "dil": "tr", "karanlik": "0",
        "tema": "indigo", "streak": "0", "son_kayit_gun": "",
        "rozetler": "[]", "hatirlatma": "0",
    }
    with conn() as c:
        for k, v in defaults.items():
            c.execute("INSERT OR IGNORE INTO ayarlar (key, value) VALUES (?, ?)", (k, v))


def _migrate_json():
    if not JSON_PATH.exists():
        return
    with conn() as c:
        n = c.execute("SELECT COUNT(*) FROM kayitlar").fetchone()[0]
        if n > 0:
            return
    raw = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        data = {"kayitlar": raw, "ayarlar": {}, "tekrarlayan": [], "favoriler": []}
    else:
        data = raw
    with conn() as c:
        for k in data.get("kayitlar", []):
            c.execute("""INSERT INTO kayitlar (id,tarih,aciklama,tutar,kategori,notes,tip,tekrar_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (k.get("id"), k["tarih"], k["aciklama"], k["tutar"],
                 k.get("kategori", "diger"), k.get("notes", k.get("not", "")), k.get("tip", "gider"), k.get("tekrar_id")))
        for f in data.get("favoriler", []):
            c.execute("INSERT INTO favoriler (id,aciklama,tutar,kategori,tip) VALUES (?,?,?,?,?)",
                      (f.get("id"), f["aciklama"], f["tutar"], f.get("kategori", "diger"), f.get("tip", "gider")))
        for t in data.get("tekrarlayan", []):
            c.execute("INSERT INTO tekrarlayan (id,aciklama,tutar,kategori,tip,gun) VALUES (?,?,?,?,?,?)",
                      (t.get("id"), t["aciklama"], t["tutar"], t.get("kategori", "diger"), t.get("tip", "gider"), t.get("gun", 1)))
        for key, val in data.get("ayarlar", {}).items():
            c.execute("INSERT OR REPLACE INTO ayarlar (key,value) VALUES (?,?)",
                      (key, json.dumps(val) if isinstance(val, (bool, list, dict)) else str(val)))


def ayar_get(key, default=None):
    init_db()
    with conn() as c:
        row = c.execute("SELECT value FROM ayarlar WHERE key=?", (key,)).fetchone()
    if not row:
        return default
    v = row["value"]
    if v in ("True", "False"):
        return v == "True"
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return v


def ayar_set(key, value):
    init_db()
    val = json.dumps(value) if isinstance(value, (bool, list, dict)) else str(value)
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO ayarlar (key,value) VALUES (?,?)", (key, val))


def pin_kur(pin):
    ayar_set("pin_hash", _hash_pin(pin))


def pin_dogru(pin):
    h = ayar_get("pin_hash")
    if not h:
        return True
    return _hash_pin(pin) == h


def pin_var_mi():
    return bool(ayar_get("pin_hash"))


def otomatik_kategori(aciklama):
    a = aciklama.lower()
    for kelime, kat in AUTO_KAT.items():
        if kelime in a:
            return kat
    return "diger"


def _tarih(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        return datetime.min


def ekle(aciklama, tutar, kategori=None, note="", tip="gider", odeme="nakit", konum="",
         doviz="TRY", doviz_tutar=None, bolen=1, taksit_toplam=None, taksit_no=None, tekrar_id=None,
         tarih=None):
    from kur import try_cevir

    init_db()
    if not kategori:
        kategori = otomatik_kategori(aciklama)
    kaynak = float(doviz_tutar or tutar)
    tutar = try_cevir(kaynak, doviz)
    if doviz != "TRY":
        doviz_tutar = kaynak
    if tarih and len(str(tarih).strip()) >= 10:
        ts = str(tarih).strip()[:10] + " " + datetime.now().strftime("%H:%M")
    else:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with conn() as c:
        c.execute("""INSERT INTO kayitlar
            (tarih,aciklama,tutar,kategori,notes,tip,odeme,konum,doviz,doviz_tutar,bolen,taksit_toplam,taksit_no,tekrar_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ts, aciklama.strip(), tutar, kategori,
             note.strip(), tip, odeme, konum.strip(), doviz, doviz_tutar, max(1, int(bolen)),
             taksit_toplam, taksit_no, tekrar_id))
        rid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    _streak_guncelle()
    _rozet_kontrol()
    _yedek_al()
    return rid


def guncelle(kid, **kw):
    init_db()
    if "note" in kw:
        kw["notes"] = kw.pop("note")
    fields, vals = [], []
    for k, v in kw.items():
        if v is not None:
            fields.append(f"{k}=?")
            vals.append(v)
    if not fields:
        return False
    vals.append(kid)
    with conn() as c:
        c.execute(f"UPDATE kayitlar SET {','.join(fields)} WHERE id=?", vals)
    _yedek_al()
    return True


def sil(kid):
    init_db()
    with conn() as c:
        c.execute("DELETE FROM kayitlar WHERE id=?", (kid,))
    _yedek_al()
    return True


def get_kayit(kid):
    init_db()
    with conn() as c:
        r = c.execute("SELECT * FROM kayitlar WHERE id=?", (kid,)).fetchone()
    return dict(r) if r else None


def yukle():
    init_db()
    with conn() as c:
        rows = c.execute("SELECT * FROM kayitlar ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def filtrele(kayitlar, q="", kategori="", tip="", ay="", yil=""):
    sonuc = kayitlar
    if q:
        q = q.lower()
        sonuc = [k for k in sonuc if q in k["aciklama"].lower() or q in (k.get("notes") or "").lower() or q in (k.get("konum") or "").lower()]
    if kategori:
        sonuc = [k for k in sonuc if k.get("kategori") == kategori]
    if tip:
        sonuc = [k for k in sonuc if k.get("tip", "gider") == tip]
    if ay and yil:
        p = f"{yil}-{int(ay):02d}"
        sonuc = [k for k in sonuc if k["tarih"].startswith(p)]
    elif yil:
        sonuc = [k for k in sonuc if k["tarih"].startswith(str(yil))]
    return sonuc


def sirala(kayitlar, mode="date_desc"):
    key_fn = {
        "date_desc": lambda k: _tarih(k["tarih"]),
        "date_asc": lambda k: _tarih(k["tarih"]),
        "amount_desc": lambda k: k["tutar"],
        "amount_asc": lambda k: k["tutar"],
    }.get(mode, lambda k: _tarih(k["tarih"]))
    return sorted(kayitlar, key=key_fn, reverse=mode in ("date_desc", "amount_desc"))


def donem_toplam(kayitlar, bas, bit):
    g = gi = 0.0
    for k in kayitlar:
        t = _tarih(k["tarih"])
        if bas <= t <= bit:
            if k.get("tip", "gider") == "gelir":
                gi += k["tutar"]
            else:
                g += k["tutar"]
    return g, gi


def bugun_toplam(kayitlar=None):
    now = datetime.now()
    bas = now.replace(hour=0, minute=0, second=0)
    bit = now.replace(hour=23, minute=59, second=59)
    return donem_toplam(kayitlar or yukle(), bas, bit)


def ay_toplam(kayitlar=None, yil=None, ay=None):
    now = datetime.now()
    yil, ay = yil or now.year, ay or now.month
    bas = datetime(yil, ay, 1)
    bit = datetime(yil + 1, 1, 1) - timedelta(seconds=1) if ay == 12 else datetime(yil, ay + 1, 1) - timedelta(seconds=1)
    return donem_toplam(kayitlar or yukle(), bas, bit)


def hafta_toplam(kayitlar=None):
    now = datetime.now()
    bas = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    bit = bas + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return donem_toplam(kayitlar or yukle(), bas, bit)


def yil_toplam(kayitlar=None, yil=None):
    yil = yil or datetime.now().year
    return donem_toplam(kayitlar or yukle(), datetime(yil, 1, 1), datetime(yil, 12, 31, 23, 59, 59))


def gecen_ay_karsilastir(yil, ay):
    g, _ = ay_toplam(yil=yil, ay=ay)
    if ay == 1:
        pg, _ = ay_toplam(yil=yil - 1, ay=12)
    else:
        pg, _ = ay_toplam(yil=yil, ay=ay - 1)
    if pg == 0:
        return 0, g, pg
    return round((g - pg) / pg * 100, 1), g, pg


def ortalama_gunluk(yil, ay):
    g, _ = ay_toplam(yil=yil, ay=ay)
    now = datetime.now()
    gun = now.day if (now.year == yil and now.month == ay) else 30
    return round(g / max(gun, 1), 2)


def en_pahali(limit=10, yil=None, ay=None):
    k = yukle()
    if yil and ay:
        p = f"{yil}-{int(ay):02d}"
        k = [x for x in k if x["tarih"].startswith(p) and x.get("tip") == "gider"]
    else:
        k = [x for x in k if x.get("tip") == "gider"]
    return sorted(k, key=lambda x: x["tutar"], reverse=True)[:limit]


def aliskanliklar():
    from collections import Counter
    c = Counter()
    for k in yukle():
        if k.get("tip") == "gider":
            c[k["aciklama"].lower()] += 1
    return [{"aciklama": a, "sayi": n} for a, n in c.most_common(5) if n >= 3]


def kategori_dagilimi(yil, ay):
    p = f"{yil}-{int(ay):02d}"
    d = {}
    for k in yukle():
        if k.get("tip") != "gider" or not k["tarih"].startswith(p):
            continue
        cat = k.get("kategori", "diger")
        d[cat] = d.get(cat, 0) + k["tutar"]
    return d


def gunluk_trend(gun=7):
    now = datetime.now()
    out = []
    for i in range(gun - 1, -1, -1):
        d = now - timedelta(days=i)
        bas = d.replace(hour=0, minute=0, second=0, microsecond=0)
        bit = d.replace(hour=23, minute=59, second=59, microsecond=0)
        g, gi = donem_toplam(yukle(), bas, bit)
        out.append({"gun": d.strftime("%d.%m"), "gider": g, "gelir": gi})
    return out


def ay_cift_karsilastir(yil, ay):
    g1, _ = ay_toplam(yil=yil, ay=ay)
    if ay == 1:
        g2, _ = ay_toplam(yil=yil - 1, ay=12)
        pa = 12
        py = yil - 1
    else:
        g2, _ = ay_toplam(yil=yil, ay=ay - 1)
        pa, py = ay - 1, yil
    return {"bu_ay": ay, "bu_yil": yil, "bu_gider": g1, "gecen_ay": pa, "gecen_yil": py, "gecen_gider": g2}


def tum_emoji_map():
    m = dict(KATEGORI_EMOJI)
    custom = ayar_get("kat_emoji", {})
    if isinstance(custom, dict):
        m.update(custom)
    init_db()
    with conn() as c:
        for r in c.execute("SELECT ad, emoji FROM ozel_kategoriler"):
            m[r["ad"]] = r["emoji"]
    return m


def kategori_emoji_kaydet(kategori, emoji):
    m = ayar_get("kat_emoji", {})
    if not isinstance(m, dict):
        m = {}
    m[kategori] = emoji.strip() or KATEGORI_EMOJI.get(kategori, "📦")
    ayar_set("kat_emoji", m)


def sablon_listesi():
    return ayar_get("sablonlar", []) or []


def sablon_ekle(aciklama, tutar, kategori="diger"):
    lst = sablon_listesi()
    lst.append({"aciklama": aciklama.strip(), "tutar": round(float(tutar), 2), "kategori": kategori})
    ayar_set("sablonlar", lst[-20:])


def sablon_sil(idx):
    lst = sablon_listesi()
    if 0 <= idx < len(lst):
        lst.pop(idx)
        ayar_set("sablonlar", lst)


def pdf_rapor_bytes(lang="tr"):
    from fpdf import FPDF
    now = datetime.now()
    g, gi = ay_toplam(yil=now.year, ay=now.month)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    title = "Expense Report" if lang == "en" else "Harcama Raporu"
    pdf.cell(0, 12, f"{title} - {now.strftime('%Y-%m')}", ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, f"Gider / Expense: {g:.2f} TL", ln=True)
    pdf.cell(0, 8, f"Gelir / Income: {gi:.2f} TL", ln=True)
    pdf.cell(0, 8, f"Net: {gi - g:.2f} TL", ln=True)
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Son kayitlar / Recent:", ln=True)
    pdf.set_font("Helvetica", size=10)
    for k in reversed(yukle()[-30:]):
        line = f"{k['tarih'][:10]}  {k['aciklama'][:30]}  {k['tutar']:.2f} TL"
        pdf.cell(0, 6, line.encode("latin-1", "replace").decode("latin-1"), ln=True)
    return bytes(pdf.output(dest="S"))


def aylik_trend(n=6):
    now = datetime.now()
    y, m = now.year, now.month
    out = []
    for _ in range(n):
        g, gi = ay_toplam(yil=y, ay=m)
        out.append({"yil": y, "ay": m, "gider": g, "gelir": gi})
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    out.reverse()
    return out


def heatmap(yil=None):
    yil = yil or datetime.now().year
    d = {}
    for k in yukle():
        if k.get("tip") != "gider":
            continue
        t = _tarih(k["tarih"])
        if t.year != yil:
            continue
        key = t.strftime("%Y-%m-%d")
        d[key] = d.get(key, 0) + k["tutar"]
    return d


def kategori_limit_asimi(yil, ay):
    dag = kategori_dagilimi(yil, ay)
    init_db()
    with conn() as c:
        limits = {r["kategori"]: r["max_tutar"] for r in c.execute("SELECT * FROM kategori_limitleri").fetchall()}
    return {k: v for k, v in dag.items() if k in limits and v > limits[k]}


def kategori_limit_kaydet(kategori, limit):
    init_db()
    with conn() as c:
        if limit <= 0:
            c.execute("DELETE FROM kategori_limitleri WHERE kategori=?", (kategori,))
        else:
            c.execute("INSERT OR REPLACE INTO kategori_limitleri VALUES (?,?)", (kategori, limit))


def ozel_kategori_ekle(ad, emoji="📌"):
    init_db()
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO ozel_kategoriler VALUES (?,?)", (ad.strip(), emoji))


def tum_kategoriler():
    init_db()
    with conn() as c:
        oz = [r["ad"] for r in c.execute("SELECT ad FROM ozel_kategoriler").fetchall()]
    return list(dict.fromkeys(["yemek", "ulasim", "eglence", "konut", "saglik", "diger"] + oz))


def favori_listesi():
    init_db()
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM favoriler").fetchall()]


def favori_ekle(aciklama, tutar, kategori="diger", tip="gider", odeme="nakit"):
    init_db()
    with conn() as c:
        c.execute("INSERT INTO favoriler (aciklama,tutar,kategori,tip,odeme) VALUES (?,?,?,?,?)",
                  (aciklama, round(float(tutar), 2), kategori, tip, odeme))


def favori_sil(fid):
    init_db()
    with conn() as c:
        c.execute("DELETE FROM favoriler WHERE id=?", (fid,))


def hizli_ekle_listesi(limit=5):
    seen = {}
    for k in reversed(yukle()):
        key = (k["aciklama"], k.get("kategori"), k.get("tip"), k.get("odeme", "nakit"))
        if key not in seen:
            seen[key] = k
        if len(seen) >= limit:
            break
    return list(seen.values())


def son_kayit():
    k = yukle()
    return k[-1] if k else None


def borc_ekle(kime, tutar, note=""):
    init_db()
    with conn() as c:
        c.execute("INSERT INTO borclar (kime,tutar,notes) VALUES (?,?,?)", (kime, float(tutar), note))


def borc_listesi():
    init_db()
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM borclar").fetchall()]


def borc_ode(bid, miktar):
    init_db()
    with conn() as c:
        c.execute("UPDATE borclar SET odenen=odenen+? WHERE id=?", (float(miktar), bid))


def borc_sil(bid):
    init_db()
    with conn() as c:
        c.execute("DELETE FROM borclar WHERE id=?", (bid,))


def tekrarlayan_ekle(aciklama, tutar, kategori="diger", tip="gider", gun=1, odeme="nakit"):
    init_db()
    with conn() as c:
        c.execute("INSERT INTO tekrarlayan (aciklama,tutar,kategori,tip,gun,odeme) VALUES (?,?,?,?,?,?)",
                  (aciklama, float(tutar), kategori, tip, max(1, min(28, int(gun))), odeme))


def tekrarlayan_listesi():
    init_db()
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM tekrarlayan").fetchall()]


def tekrarlayan_sil(tid):
    init_db()
    with conn() as c:
        c.execute("DELETE FROM tekrarlayan WHERE id=?", (tid,))


def tekrarlayan_uygula():
    init_db()
    now = datetime.now()
    key = now.strftime("%Y-%m")
    for t in tekrarlayan_listesi():
        if now.day < t.get("gun", 1):
            continue
        var = any(k.get("tekrar_id") == t["id"] and k["tarih"].startswith(key) for k in yukle())
        if not var:
            ekle(t["aciklama"], t["tutar"], t["kategori"], tip=t["tip"], odeme=t.get("odeme", "nakit"), tekrar_id=t["id"])


def _streak_guncelle():
    bugun = datetime.now().strftime("%Y-%m-%d")
    son = ayar_get("son_kayit_gun", "")
    streak = int(ayar_get("streak", 0))
    if son == bugun:
        return
    dun = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    streak = streak + 1 if son == dun else 1
    ayar_set("streak", streak)
    ayar_set("son_kayit_gun", bugun)


def _rozet_kontrol():
    rozetler = set(ayar_get("rozetler", []))
    streak = int(ayar_get("streak", 0))
    if streak >= 7:
        rozetler.add("streak7")
    g, _ = ay_toplam()
    butce = float(ayar_get("butce", 0))
    if butce > 0 and g <= butce:
        rozetler.add("butce")
    if len(yukle()) >= 50:
        rozetler.add("kayit50")
    ayar_set("rozetler", list(rozetler))


def rozetler():
    return ayar_get("rozetler", [])


def _yedek_al():
    yedek_dir = BASE / "yedekler"
    yedek_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = yedek_dir / f"yedek_{ts}.json"
    dst.write_text(json.dumps(export_veri(), ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(yedek_dir.glob("yedek_*.json"), reverse=True)
    for f in files[10:]:
        f.unlink(missing_ok=True)


def export_veri():
    init_db()
    return {
        "ayarlar": {k: ayar_get(k) for k in ["butce", "hafta_butce", "tasarruf_hedef", "usd_kur", "eur_kur", "dil", "karanlik", "tema", "streak", "rozetler"]},
        "kayitlar": yukle(),
        "favoriler": favori_listesi(),
        "tekrarlayan": tekrarlayan_listesi(),
        "borclar": borc_listesi(),
    }


def yedek_yukle(data):
    init_db()
    with conn() as c:
        c.executescript("DELETE FROM kayitlar; DELETE FROM favoriler; DELETE FROM tekrarlayan; DELETE FROM borclar;")
    for k in data.get("kayitlar", []):
        with conn() as db:
            db.execute("""INSERT INTO kayitlar (id,tarih,aciklama,tutar,kategori,notes,tip,odeme,konum,doviz,bolen,tekrar_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (k.get("id"), k["tarih"], k["aciklama"], k["tutar"], k.get("kategori", "diger"),
                 k.get("notes", ""), k.get("tip", "gider"), k.get("odeme", "nakit"),
                 k.get("konum", ""), k.get("doviz", "TRY"), k.get("bolen", 1), k.get("tekrar_id")))
    for key, val in data.get("ayarlar", {}).items():
        ayar_set(key, val)


def csv_icerik(kayitlar=None):
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "tarih", "aciklama", "tutar", "kategori", "notes", "tip", "odeme", "konum", "doviz", "bolen"])
    for k in (kayitlar or yukle()):
        w.writerow([k["id"], k["tarih"], k["aciklama"], k["tutar"], k.get("kategori"), k.get("notes"),
                    k.get("tip"), k.get("odeme"), k.get("konum"), k.get("doviz"), k.get("bolen", 1)])
    return buf.getvalue()
