#!/usr/bin/env python3
import json
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, session, url_for, Response

import harcama as h
from i18n import t, KATEGORILER

app = Flask(__name__)
app.secret_key = "harcama-notu-local"

CHART_RENK = {
    "yemek": "#f59e0b", "ulasim": "#3b82f6", "eglence": "#a855f7",
    "konut": "#ef4444", "saglik": "#22c55e", "diger": "#6b7280",
}

AY_ADLARI_TR = ["", "Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
AY_ADLARI_EN = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _lang():
    return session.get("lang", h.ayar_get("dil", "tr"))


def _karanlik():
    val = session.get("karanlik")
    if val is None:
        return bool(h.ayar_get("karanlik", False))
    return bool(val)


def _tx(lang):
    return lambda key: t(lang, key)


def _parse_amount(raw):
    val = float(str(raw).replace(",", "."))
    if val <= 0:
        raise ValueError
    return val


def _filtre_params():
    now = datetime.now()
    if request.method == "GET" and "ay" not in request.args and "yil" not in request.args:
        return str(now.month), str(now.year), False
    ay = request.values.get("ay", "")
    yil = request.values.get("yil") or str(now.year)
    return ay, yil, ay == ""


def _redirect(msg, **extra):
    ay, yil, tum = _filtre_params()
    params = {"msg": msg, "lang": _lang()}
    if tum:
        params["ay"] = ""
    elif ay:
        params["ay"], params["yil"] = ay, yil
    if yil:
        params.setdefault("yil", yil)
    params.update(extra)
    return redirect(url_for("ana", **params))


def _ana_context(lang, **extra):
    kayitlar = h.yukle()
    q = request.args.get("q", "")
    kat = request.args.get("kat", "")
    tip_f = request.args.get("tip_f", "")
    sort = request.args.get("sort", "date_desc")
    ay, yil, tum = _filtre_params()
    sel_yil = int(yil) if yil else datetime.now().year
    sel_ay = int(ay) if ay and not tum else None

    filtre = h.filtrele(kayitlar, q, kat, tip_f, "" if tum else ay, yil)
    filtre = h.sirala(filtre, sort)

    if sel_ay:
        gider, gelir = h.ay_toplam(kayitlar, sel_yil, sel_ay)
        chart = h.kategori_dagilimi(kayitlar, sel_yil, sel_ay)
    else:
        gider, gelir = h.yil_toplam(kayitlar, sel_yil)
        chart = {}
        for m in range(1, 13):
            d = h.kategori_dagilimi(kayitlar, sel_yil, m)
            for c, v in d.items():
                chart[c] = chart.get(c, 0) + v

    net = gelir - gider
    h_g, h_gi = h.hafta_toplam(kayitlar)
    y_g, y_gi = h.yil_toplam(kayitlar, sel_yil)
    butce = float(h.ayar_get("butce", 0) or 0)
    butce_kalan = butce - gider if butce > 0 else 0
    butce_yuzde = min(100, (gider / butce * 100)) if butce > 0 else 0
    chart_total = sum(chart.values()) or 1
    trend = h.aylik_trend(6)
    trend_max = max((max(x["gider"], x["gelir"]) for x in trend), default=1) or 1

    edit_id = request.args.get("edit", type=int)
    duzenle = h.get_kayit(edit_id) if edit_id else None
    tx = _tx(lang)
    ay_adlari = AY_ADLARI_EN if lang == "en" else AY_ADLARI_TR

    msg_key = request.args.get("msg")
    basari = tx(msg_key) if msg_key else None

    sort_opts = {
        "date_desc": tx("sort_date_desc"), "date_asc": tx("sort_date_asc"),
        "amount_desc": tx("sort_amount_desc"), "amount_asc": tx("sort_amount_asc"),
    }
    return dict(
        lang=lang, karanlik=_karanlik(), tx=tx, kategoriler=KATEGORILER,
        kayitlar=filtre, q=q, kat=kat, tip_f=tip_f, sort=sort, sort_opts=sort_opts,
        ay=ay, yil=yil, tum=tum, sel_ay=sel_ay, sel_yil=sel_yil, ay_adlari=ay_adlari,
        gider=gider, gelir=gelir, net=net, h_gider=h_g, h_gelir=h_gi, y_gider=y_g, y_gelir=y_gi,
        butce=butce, butce_kalan=butce_kalan, butce_asildi=butce > 0 and gider > butce,
        butce_yuzde=butce_yuzde, chart=chart, chart_total=chart_total, chart_renk=CHART_RENK,
        trend=trend, trend_max=trend_max,
        hizli=h.hizli_ekle_listesi(), favoriler=h.favori_listesi(),
        tekrarlayan=h.yukle_veri()["tekrarlayan"],
        duzenle=duzenle, hata=extra.get("hata"), basari=basari,
    )


@app.before_request
def _tekrarlayan():
    h.tekrarlayan_uygula()


@app.route("/")
def ana():
    if request.args.get("lang") in ("tr", "en"):
        session["lang"] = request.args["lang"]
        h.ayar_set("dil", request.args["lang"])
    return render_template("index.html", **_ana_context(_lang()))


@app.post("/theme")
def theme_kaydet():
    data = request.get_json(silent=True) or {}
    val = bool(data.get("dark"))
    session["karanlik"] = val
    h.ayar_set("karanlik", val)
    return jsonify(ok=True, dark=val)


@app.post("/ekle")
def ekle_form():
    try:
        aciklama = request.form.get("aciklama", "").strip()
        if not aciklama:
            raise ValueError("required")
        tutar = _parse_amount(request.form["tutar"])
        h.ekle(aciklama, tutar, request.form.get("kategori", "diger"),
               request.form.get("not", ""), request.form.get("tip", "gider"))
    except (ValueError, KeyError):
        return render_template("index.html", **_ana_context(_lang(), hata=t(_lang(), "invalid_amount")))
    return _redirect("msg_added")


@app.post("/guncelle/<int:kayit_id>")
def guncelle_form(kayit_id):
    try:
        aciklama = request.form.get("aciklama", "").strip()
        if not aciklama:
            raise ValueError
        tutar = _parse_amount(request.form["tutar"])
        if not h.guncelle(kayit_id, aciklama, tutar, request.form.get("kategori", "diger"),
                          request.form.get("not", ""), request.form.get("tip", "gider")):
            return render_template("index.html", **_ana_context(_lang(), hata=t(_lang(), "not_found")))
    except (ValueError, KeyError):
        return render_template("index.html", **_ana_context(_lang(), hata=t(_lang(), "invalid_amount")))
    return _redirect("msg_updated")


@app.post("/sil/<int:kayit_id>")
def sil_form(kayit_id):
    h.sil(kayit_id)
    return _redirect("msg_deleted")


@app.post("/favori")
def favori_ekle_form():
    try:
        h.favori_ekle(request.form["aciklama"], _parse_amount(request.form["tutar"]),
                      request.form.get("kategori", "diger"), request.form.get("tip", "gider"))
    except (ValueError, KeyError):
        pass
    return _redirect("msg_saved")


@app.post("/favori/<int:fav_id>/sil")
def favori_sil_form(fav_id):
    h.favori_sil(fav_id)
    return _redirect("msg_deleted")


@app.post("/tekrar")
def tekrar_ekle():
    try:
        h.tekrarlayan_ekle(request.form["aciklama"], _parse_amount(request.form["tutar"]),
                           request.form.get("kategori", "diger"), request.form.get("tip", "gider"),
                           request.form.get("gun", 1))
    except (ValueError, KeyError):
        pass
    return _redirect("msg_saved")


@app.post("/tekrar/<int:item_id>/sil")
def tekrar_sil(item_id):
    h.tekrarlayan_sil(item_id)
    return _redirect("msg_deleted")


@app.post("/ayarlar")
def ayarlar_kaydet():
    try:
        h.ayar_set("butce", max(0, float(request.form.get("butce", 0) or 0)))
    except ValueError:
        pass
    return _redirect("msg_saved")


@app.get("/csv")
def csv_indir():
    return Response(h.csv_icerik(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=harcamalar.csv"})


@app.get("/yedek")
def yedek_indir():
    return Response(json.dumps(h.yukle_veri(), ensure_ascii=False, indent=2),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=harcamalar-yedek.json"})


@app.post("/yedek")
def yedek_yukle_form():
    f = request.files.get("dosya")
    if not f:
        return redirect(url_for("ana"))
    try:
        h.yedek_yukle(json.loads(f.read().decode("utf-8")))
    except (json.JSONDecodeError, ValueError):
        return render_template("index.html", **_ana_context(_lang(), hata=t(_lang(), "invalid_amount")))
    return _redirect("msg_restored")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    print(f"Tarayicida ac: http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
