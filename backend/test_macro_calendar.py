"""
Ekonomik takvim (macro_calendar.py) testi. Veritabani/sunucu gerektirmez.

Calistir: python test_macro_calendar.py
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from macro_calendar import etkinlikler
from market_hours import BIST_HOLIDAYS

ok = fail = 0


def check(ad, kosul, ek=""):
    global ok, fail
    if kosul:
        ok += 1
        print("OK  ", ad)
    else:
        fail += 1
        print("FAIL", ad, ek)


def bul(liste, baslik, ay=None):
    return [e for e in liste if e["baslik"].startswith(baslik) and (ay is None or e["tarih"].month == ay)]


# 1) TUFE her ayin 3'u; hafta sonuna denk gelirse sonraki is gunu.
#    2026-10-03 Cumartesi -> 2026-10-05 Pazartesi.
liste = etkinlikler(date(2026, 9, 25), 90)
tufe_ekim = bul(liste, "TÜFE (Enflasyon)", 10)
check("TÜFE Ekim: hafta sonu -> Pazartesi 5 Ekim", len(tufe_ekim) == 1 and tufe_ekim[0]["tarih"] == date(2026, 10, 5), tufe_ekim)
tufe_kasim = bul(liste, "TÜFE (Enflasyon)", 11)
check("TÜFE Kasım: 3 Kasım Salı", len(tufe_kasim) == 1 and tufe_kasim[0]["tarih"] == date(2026, 11, 3), tufe_kasim)
check("TÜFE kesin tarihli (tahmini=False)", all(not e["tahmini"] for e in tufe_ekim + tufe_kasim))

# 2) Hicbir Turkiye etkinligi hafta sonu ya da borsa tatiline denk gelmez.
turkiye = [e for e in etkinlikler(date(2026, 1, 1), 360) if e["kategori"] == "TURKIYE"]
check("Türkiye etkinlikleri iş gününe denk geliyor",
      all(e["tarih"].weekday() < 5 and e["tarih"] not in BIST_HOLIDAYS for e in turkiye),
      [e["tarih"] for e in turkiye if e["tarih"].weekday() >= 5 or e["tarih"] in BIST_HOLIDAYS])

# 3) NFP her zaman Cuma ve ayin ilk 7 gunu icinde.
nfp = [e for e in etkinlikler(date(2026, 1, 1), 360) if e["baslik"].startswith("ABD Tarım")]
check("NFP: 12 ay, hepsi Cuma ve ayın ilk haftası",
      len(nfp) == 12 and all(e["tarih"].weekday() == 4 and e["tarih"].day <= 7 for e in nfp), [e["tarih"] for e in nfp])

# 4) GSYH yalnizca ceyrek aylarinda.
gsyh = [e for e in etkinlikler(date(2026, 1, 1), 360) if e["baslik"].startswith("GSYH")]
check("GSYH yalnızca Mart/Haziran/Eylül/Aralık", {e["tarih"].month for e in gsyh} <= {3, 6, 9, 12} and len(gsyh) == 4,
      [e["tarih"] for e in gsyh])

# 5) Tatil bloklari: Kurban Bayrami (26-30 Mayis 2026) tek satir, 5 gun.
tatiller = [e for e in etkinlikler(date(2026, 5, 1), 40) if e["kategori"] == "TATIL"]
kurban = [e for e in tatiller if e["tarih"] == date(2026, 5, 26)]
check("Kurban Bayramı tek blok halinde", len(kurban) == 1 and "5 gün" in kurban[0]["aciklama"], tatiller)
check("Tatiller blok halinde (1 Mayıs, 19 Mayıs, Kurban = 3 satır)", len(tatiller) == 3, [e["tarih"] for e in tatiller])

# 6) Sonuclar tarihe gore sirali ve aralik disina tasmaz.
bas = date(2026, 9, 25)
liste = etkinlikler(bas, 45)
tarihler = [e["tarih"] for e in liste]
check("sıralı", tarihler == sorted(tarihler))
check("aralık içinde", all(bas <= t <= bas + timedelta(days=45) for t in tarihler))

# 7) Yil sonu gecisi (Aralik -> Ocak) hata vermez, Ocak etkinlikleri gelir.
gecis = etkinlikler(date(2026, 12, 20), 30)
check("yıl geçişi: Ocak 2027 etkinlikleri var", any(e["tarih"].year == 2027 for e in gecis))

# 8) Katilim ilkesi: faiz karari satiri KESINLIKLE yok.
tum = etkinlikler(date(2026, 1, 1), 360)
metin = " ".join((e["baslik"] + " " + e["aciklama"]).lower() for e in tum)
check("faiz/PPK/Fed satırı yok", not any(k in metin for k in ("faiz", "ppk", "fed ", "mevduat")), metin[:120])

# 9) Onem 1-3 araliginda, aciklama bos degil.
check("önem 1-3 ve açıklama dolu", all(1 <= e["onem"] <= 3 and e["aciklama"].strip() for e in tum))

print(f"\n{ok} basarili, {fail} basarisiz")
sys.exit(1 if fail else 0)
