"""Canli doviz kurlari (USD/EUR -> TRY)."""
import json
import urllib.request
from datetime import datetime, timedelta

CACHE_SAAT = 1
API = "https://open.er-api.com/v6/latest/USD"


def _fetch():
    req = urllib.request.Request(API, headers={"User-Agent": "harcama-notu/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode())
    if data.get("result") != "success":
        raise ValueError("kur api hatasi")
    rates = data["rates"]
    usd = round(float(rates["TRY"]), 4)
    eur = round(float(rates["TRY"]) / float(rates["EUR"]), 4)
    return usd, eur


def canli_kurlar():
    from storage import ayar_get, ayar_set

    cached = ayar_get("kur_cache")
    if isinstance(cached, dict) and cached.get("ts"):
        try:
            ts = datetime.fromisoformat(cached["ts"])
            if datetime.now() - ts < timedelta(hours=CACHE_SAAT):
                return float(cached["usd"]), float(cached["eur"])
        except (ValueError, TypeError):
            pass
    try:
        usd, eur = _fetch()
        ayar_set("kur_cache", {"usd": usd, "eur": eur, "ts": datetime.now().isoformat()})
        ayar_set("usd_kur", usd)
        ayar_set("eur_kur", eur)
        return usd, eur
    except Exception:
        return float(ayar_get("usd_kur", 34) or 34), float(ayar_get("eur_kur", 37) or 37)


def try_cevir(tutar, doviz):
    if doviz == "TRY":
        return round(float(tutar), 2)
    usd, eur = canli_kurlar()
    kur = usd if doviz == "USD" else eur
    return round(float(tutar) * kur, 2)
