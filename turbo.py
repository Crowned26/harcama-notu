"""Turbo mod — hizli dis yikama fiyatlari."""

NAKIT_INDIRIM = 100

FIYATLAR = {
    "otomobil": 700,
    "suv": 800,
    "panelvan": 800,
}

ARAC_ETIKET = {
    "tr": {"otomobil": "Otomobil", "suv": "SUV", "panelvan": "Ticari Panelvan"},
    "en": {"otomobil": "Car", "suv": "SUV", "panelvan": "Commercial van"},
}


def yikama_fiyat(arac, odeme="kart"):
    base = FIYATLAR.get(arac, 700)
    if odeme == "nakit":
        return base - NAKIT_INDIRIM
    return base


def yikama_aciklama(arac, odeme, lang="tr"):
    etiket = ARAC_ETIKET.get(lang, ARAC_ETIKET["tr"]).get(arac, arac)
    return f"Dis yikama - {etiket}"
