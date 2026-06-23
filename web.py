#!/usr/bin/env python3
import json
import os
from datetime import datetime
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, session, url_for, Response

import storage as s
from i18n import t
import turbo as tb

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "harcama-notu-local-change-me")

CHART_RENK = {"yemek": "#f59e0b", "ulasim": "#3b82f6", "eglence": "#a855f7", "konut": "#ef4444", "saglik": "#22c55e", "diger": "#6b7280"}
AY_TR = ["", "Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
AY_EN = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TEMAS = ["indigo", "emerald", "rose", "amber"]


def _lang():
    return session.get("lang", s.ayar_get("dil", "tr") or "tr")


def _tx(lang):
    return lambda k: t(lang, k)


def _parse_amount(raw):
    v = float(str(raw).replace(",", "."))
    if v <= 0:
        raise ValueError
    return v


def _filtre_params():
    now = datetime.now()
    if request.method == "GET" and "ay" not in request.args and "yil" not in request.args:
        return str(now.month), str(now.year), False
    ay = request.values.get("ay", "")
    yil = request.values.get("yil") or str(now.year)
    return ay, yil, ay == ""


def _redirect(msg, **extra):
    ay, yil, tum = _filtre_params()
    p = {"msg": msg, "lang": _lang()}
    if tum or not ay:
        p["ay"], p["yil"] = str(datetime.now().month), yil or str(datetime.now().year)
    else:
        p["ay"], p["yil"] = ay, yil
    p.update(extra)
    return redirect(url_for("ana", **{k: v for k, v in p.items() if v is not None}))


def pin_gerekli(f):
    @wraps(f)
    def inner(*a, **kw):
        if s.pin_var_mi() and not session.get("unlocked"):
            return redirect(url_for("pin_sayfa"))
        return f(*a, **kw)
    return inner


def _ctx(lang, **extra):
    kayitlar = s.yukle()
    q = request.args.get("q", "")
    kat = request.args.get("kat", "")
    tip_f = request.args.get("tip_f", "")
    sort = request.args.get("sort", "date_desc")
    tab = request.args.get("tab", "home")
    ay, yil, tum = _filtre_params()
    sel_yil = int(yil)
    sel_ay = int(ay) if ay else None
    filtre = s.sirala(s.filtrele(kayitlar, q, kat, tip_f, "" if tum else ay, yil), sort)
    if sel_ay:
        gider, gelir = s.ay_toplam(yil=sel_yil, ay=sel_ay)
        chart = s.kategori_dagilimi(sel_yil, sel_ay)
        karsilastirma, _, _ = s.gecen_ay_karsilastir(sel_yil, sel_ay)
        ort_gun = s.ortalama_gunluk(sel_yil, sel_ay)
    else:
        gider, gelir = s.yil_toplam(yil=sel_yil)
        chart, karsilastirma, ort_gun = {}, 0, 0
    bg, gi = s.bugun_toplam()
    hg, hi = s.hafta_toplam()
    yg, yi = s.yil_toplam(yil=sel_yil)
    butce = float(s.ayar_get("butce", 0) or 0)
    hafta_butce = float(s.ayar_get("hafta_butce", 0) or 0)
    tasarruf = float(s.ayar_get("tasarruf_hedef", 0) or 0)
    net = gelir - gider
    butce_kalan = butce - gider if butce > 0 else 0
    hafta_kalan = hafta_butce - hg if hafta_butce > 0 else 0
    gunluk = s.gunluk_trend(7)
    gunluk_max = max((x["gider"] for x in gunluk), default=1) or 1
    ay_cift = s.ay_cift_karsilastir(sel_yil, sel_ay or datetime.now().month)
    emoji_map = s.tum_emoji_map()
    trend = s.aylik_trend(6)
    trend_max = max((max(x["gider"], x["gelir"]) for x in trend), default=1) or 1
    chart_total = sum(chart.values()) or 1
    edit_id = request.args.get("edit", type=int)
    tx = _tx(lang)
    ay_ad = AY_EN if lang == "en" else AY_TR
    msg = request.args.get("msg")
    return dict(
        lang=lang, tx=tx, tab=tab, karanlik=bool(s.ayar_get("karanlik")),
        tema=s.ayar_get("tema", "indigo"), temalar=TEMAS,
        kategoriler=s.tum_kategoriler(), emoji=emoji_map,
        kayitlar=filtre, q=q, kat=kat, tip_f=tip_f, sort=sort,
        sort_opts={"date_desc": tx("sort_date_desc"), "date_asc": tx("sort_date_asc"),
                   "amount_desc": tx("sort_amount_desc"), "amount_asc": tx("sort_amount_asc")},
        ay=ay, yil=yil, tum=tum, sel_ay=sel_ay, sel_yil=sel_yil, ay_adlari=ay_ad,
        gider=gider, gelir=gelir, net=net, bugun_g=bg, bugun_gi=gi,
        h_gider=hg, h_gelir=hi, y_gider=yg, y_gelir=yi,
        butce=butce, butce_kalan=butce_kalan, butce_asildi=butce > 0 and gider > butce,
        butce_yuzde=min(100, gider / butce * 100) if butce > 0 else 0,
        hafta_butce=hafta_butce, hafta_kalan=hafta_kalan, hafta_asildi=hafta_butce > 0 and hg > hafta_butce,
        tasarruf=tasarruf, karsilastirma=karsilastirma, ort_gun=ort_gun,
        chart=chart, chart_total=chart_total, chart_renk=CHART_RENK,
        trend=trend, trend_max=trend_max, gunluk=gunluk, gunluk_max=gunluk_max,
        ay_cift=ay_cift, ay_cift_max=max(ay_cift["bu_gider"], ay_cift["gecen_gider"], 1),
        sablonlar=s.sablon_listesi(),
        top10=s.en_pahali(10, sel_yil, sel_ay), aliskanliklar=s.aliskanliklar(),
        heatmap=s.heatmap(sel_yil), limit_asim=s.kategori_limit_asimi(sel_yil, sel_ay or datetime.now().month),
        hizli=s.hizli_ekle_listesi(), favoriler=s.favori_listesi(), son=s.son_kayit(),
        tekrarlayan=s.tekrarlayan_listesi(), borclar=s.borc_listesi(),
        rozetler=s.rozetler(), streak=int(s.ayar_get("streak", 0)),
        duzenle=s.get_kayit(edit_id) if edit_id else None,
        usd=s.ayar_get("usd_kur", 34), eur=s.ayar_get("eur_kur", 37),
        hatirlatma=int(s.ayar_get("hatirlatma", 0) or 0),
        pin_var=s.pin_var_mi(), basari=tx(msg) if msg else None, hata=extra.get("hata"),
    )


@app.before_request
def _init():
    s.init_db()
    s.tekrarlayan_uygula()


@app.route("/pin", methods=["GET", "POST"])
def pin_sayfa():
    lang = _lang()
    if request.method == "POST":
        if s.pin_dogru(request.form.get("pin", "")):
            session["unlocked"] = True
            return redirect(url_for("ana"))
        return render_template("pin.html", tx=_tx(lang), lang=lang, hata=t(lang, "pin_wrong"))
    return render_template("pin.html", tx=_tx(lang), lang=lang, hata=None)


@app.route("/")
@pin_gerekli
def ana():
    if request.args.get("lang") in ("tr", "en"):
        session["lang"] = request.args["lang"]
        s.ayar_set("dil", request.args["lang"])
    return render_template("index.html", **_ctx(_lang()))


@app.post("/theme")
def theme_kaydet():
    d = request.get_json(silent=True) or {}
    s.ayar_set("karanlik", bool(d.get("dark")))
    if d.get("tema"):
        s.ayar_set("tema", d["tema"])
    return jsonify(ok=True)


@app.post("/turbo/yikama")
@pin_gerekli
def turbo_yikama():
    arac = request.form.get("arac", "otomobil")
    odeme = request.form.get("odeme", "kart")
    if arac not in tb.FIYATLAR:
        arac = "otomobil"
    if odeme not in ("nakit", "kart"):
        odeme = "kart"
    lang = _lang()
    tutar = tb.yikama_fiyat(arac, odeme)
    s.ekle(tb.yikama_aciklama(arac, odeme, lang), tutar, "ulasim",
           note="Turbo", tip="gider", odeme=odeme)
    return _redirect("msg_added", tab="turbo")


@app.post("/ekle")
@pin_gerekli
def ekle_form():
    try:
        aciklama = request.form.get("aciklama", "").strip()
        if not aciklama:
            raise ValueError
        tutar = _parse_amount(request.form["tutar"])
        s.ekle(aciklama, tutar, request.form.get("kategori") or None,
               request.form.get("not", ""), request.form.get("tip", "gider"),
               request.form.get("odeme", "nakit"), request.form.get("konum", ""),
               request.form.get("doviz", "TRY"), request.form.get("doviz_tutar") or None,
               int(request.form.get("bolen", 1) or 1),
               int(request.form["taksit"]) if request.form.get("taksit") else None, None)
    except (ValueError, KeyError):
        return render_template("index.html", **_ctx(_lang(), hata=t(_lang(), "invalid_amount")))
    return _redirect("msg_added")


@app.post("/tekrar-son")
@pin_gerekli
def tekrar_son():
    k = s.son_kayit()
    if k:
        s.ekle(k["aciklama"], k["tutar"], k.get("kategori"), k.get("not", ""), k.get("tip", "gider"), k.get("odeme", "nakit"))
    return _redirect("msg_added")


@app.post("/guncelle/<int:kid>")
@pin_gerekli
def guncelle_form(kid):
    try:
        s.guncelle(kid, aciklama=request.form["aciklama"].strip(), tutar=_parse_amount(request.form["tutar"]),
                   kategori=request.form.get("kategori"), note=request.form.get("not", ""),
                   tip=request.form.get("tip"), odeme=request.form.get("odeme"), konum=request.form.get("konum", ""))
    except (ValueError, KeyError):
        return render_template("index.html", **_ctx(_lang(), hata=t(_lang(), "invalid_amount")))
    return _redirect("msg_updated")


@app.post("/sil/<int:kid>")
@pin_gerekli
def sil_form(kid):
    s.sil(kid)
    return _redirect("msg_deleted")


@app.post("/favori")
@pin_gerekli
def favori_ekle():
    try:
        s.favori_ekle(request.form["aciklama"], _parse_amount(request.form["tutar"]),
                      request.form.get("kategori", "diger"), request.form.get("tip", "gider"))
    except (ValueError, KeyError):
        pass
    return _redirect("msg_saved")


@app.post("/favori/<int:fid>/sil")
@pin_gerekli
def favori_sil(fid):
    s.favori_sil(fid)
    return _redirect("msg_deleted")


@app.post("/borc")
@pin_gerekli
def borc_ekle():
    s.borc_ekle(request.form["kime"], _parse_amount(request.form["tutar"]), request.form.get("not", ""))
    return _redirect("msg_saved")


@app.post("/borc/<int:bid>/ode")
@pin_gerekli
def borc_ode(bid):
    s.borc_ode(bid, _parse_amount(request.form["miktar"]))
    return _redirect("msg_saved")


@app.post("/borc/<int:bid>/sil")
@pin_gerekli
def borc_sil(bid):
    s.borc_sil(bid)
    return _redirect("msg_deleted")


@app.post("/tekrar")
@pin_gerekli
def tekrar_ekle():
    s.tekrarlayan_ekle(request.form["aciklama"], _parse_amount(request.form["tutar"]),
                       request.form.get("kategori", "diger"), request.form.get("tip", "gider"), request.form.get("gun", 1))
    return _redirect("msg_saved")


@app.post("/tekrar/<int:tid>/sil")
@pin_gerekli
def tekrar_sil(tid):
    s.tekrarlayan_sil(tid)
    return _redirect("msg_deleted")


@app.post("/ayarlar")
@pin_gerekli
def ayarlar_kaydet():
    for key in ("butce", "hafta_butce", "tasarruf_hedef", "usd_kur", "eur_kur", "hatirlatma"):
        if key in request.form:
            s.ayar_set(key, max(0, float(request.form.get(key, 0) or 0)))
    if request.form.get("pin_yeni"):
        s.pin_kur(request.form["pin_yeni"])
    if request.form.get("tema"):
        s.ayar_set("tema", request.form["tema"])
    if request.form.get("ozel_kat"):
        s.ozel_kategori_ekle(request.form["ozel_kat"], request.form.get("ozel_emoji", "📌"))
    if request.form.get("limit_kat") and request.form.get("limit_val"):
        s.kategori_limit_kaydet(request.form["limit_kat"], float(request.form["limit_val"]))
    if request.form.get("emoji_kat") and request.form.get("emoji_val"):
        s.kategori_emoji_kaydet(request.form["emoji_kat"], request.form["emoji_val"])
    if request.form.get("sablon_aciklama") and request.form.get("sablon_tutar"):
        try:
            s.sablon_ekle(request.form["sablon_aciklama"], _parse_amount(request.form["sablon_tutar"]),
                          request.form.get("sablon_kat", "diger"))
        except ValueError:
            pass
    return _redirect("msg_saved")


@app.get("/csv")
@pin_gerekli
def csv_indir():
    return Response(s.csv_icerik(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=harcamalar.csv"})


@app.get("/yedek")
@pin_gerekli
def yedek_indir():
    return Response(json.dumps(s.export_veri(), ensure_ascii=False, indent=2), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=yedek.json"})


@app.post("/yedek")
@pin_gerekli
def yedek_yukle():
    f = request.files.get("dosya")
    if f:
        s.yedek_yukle(json.loads(f.read().decode()))
    return _redirect("msg_restored")


@app.get("/pdf")
@pin_gerekli
def pdf_indir():
    data = s.pdf_rapor_bytes(_lang())
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=rapor.pdf"})


@app.post("/sablon/<int:idx>/sil")
@pin_gerekli
def sablon_sil(idx):
    s.sablon_sil(idx)
    return _redirect("msg_deleted")


@app.get("/rapor")
@pin_gerekli
def rapor():
    lang = _lang()
    now = datetime.now()
    g, gi = s.ay_toplam(yil=now.year, ay=now.month)
    return render_template("rapor.html", tx=_tx(lang), lang=lang, gider=g, gelir=gi, net=gi - g,
                           kayitlar=s.yukle()[-20:], ay=now.strftime("%Y-%m"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
