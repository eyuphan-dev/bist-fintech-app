"""
ipo_client.py
-------------
Halka arz takvimini halkarz.com'dan çeker.

NEDEN
-----
`ipos` tablosunu DOLDURAN HİÇBİR KOD YOKTU. Uygulama halka arz bölümünü
kullanıcıya gösteriyordu ama tablo her zaman boştu; arayüz de dürüstçe
"otomatik bir veri kaynağı henüz bağlı değil" yazıyordu. Bu, kullanıcıya
gösterilen ama hiç çalışmayan bir özellikti.

KAYNAK SEÇİMİ
-------------
Denenen kaynaklar:
  • KAP — halka arz bilgisini ancak şirket BORSADA İŞLEM GÖRMEYE BAŞLADIKTAN
    sonra yayımlıyor. Takvim için, yani arz ÖNCESİ dönem için işe yaramıyor.
  • İş Yatırım halka arz sayfası — 404.
  • SPK bülteni — HTML sayfası boş bir kabuk (1,4 KB), veri JavaScript ile
    yükleniyor.
  • halkarz.com — RSS besliyor ve her arz için yapısal bilgi sayfası var.
    Kullanılan kaynak bu.

KIRILGANLIK KABUL EDİLMİŞTİR
----------------------------
Bu bir HTML kazıma işlemidir; site düzenini değiştirirse ayrıştırma bozulur.
Bu yüzden ayrıştırma SAVUNMACI yazıldı: bir alan okunamazsa None bırakılır,
tahmin edilmez. Şirket adı ve kaynak bağlantısı okunamıyorsa kayıt hiç
yazılmaz — yarım bir halka arz kaydı, kayıt olmamasından kötüdür.

`is_katilim_compliant` BİLEREK DOLDURULMAZ
------------------------------------------
Halka arz olan şirketin katılım uygunluğunu bilmiyoruz; bilanço da yok, KAP
formu da (şirket henüz yükümlü değil). Varsayılan olarak "uygun değil"
göstermek, `purification_rate` yer tutucusunda yapılan hatanın aynısı olurdu:
bilmediğimiz bir şeyi iddia etmek. Alan None kalır, arayüz
"değerlendirilmedi" der.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

import models

RSS_URL = "https://halkarz.com/feed/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# Bilgi kutusundaki etiketler. Sayfa düzeni değişirse burada None döner,
# uydurma değer üretilmez.
ETIKETLER = {
    "tarih": r"Halka Arz Tarihi\s*:\s*(.+?)\s{2,}|Halka Arz Tarihi\s*:\s*([^:]+?)\s+Halka Arz Fiyat",
    "fiyat": r"Halka Arz Fiyat[ıi]/Aral[ıi][ğg][ıi]\s*:\s*([^:]+?)\s+Da[ğg][ıi]t[ıi]m",
    "dagitim": r"Da[ğg][ıi]t[ıi]m Y[öo]ntemi\s*:\s*([^:]+?)\s+Pay\s*:",
    "lot": r"Pay\s*:\s*([\d.,]+)\s*Lot",
    "aracikurum": r"Arac[ıi] Kurum\s*:\s*([^:]+?)\s+Bist Kodu",
    "sembol": r"Bist Kodu\s*:\s*([A-Z0-9]{3,6})\b",
    "pazar": r"Pazar\s*:\s*([^:]+?)\s+Bist",
}


def _duz_metin(hamsayfa: str) -> str:
    """HTML'i tek satırlık düz metne indirger; etiket eşleştirmesi bunun üstünde yapılır."""
    metin = re.sub(r"<[^>]+>", " ", hamsayfa)
    return " ".join(html.unescape(metin).split())


def tr_para(ham: Optional[str]) -> Optional[float]:
    """
    '53,60 TL' -> 53.6 ,  '1.250,00 TL' -> 1250.0 ,  '10,50 - 12,00 TL' -> 10.5

    TÜRKÇE SAYI TUZAĞI: nokta BİNLİK ayracıdır. `float("1.250")` patlamaz,
    1.25 döndürür — BİN KAT KÜÇÜK bir sayı (aynı tuzak tr_market.tr_sayi ve
    katilim_kap._sayi_coz'da da belgeli).

    Aralık verilmişse ("10,50 - 12,00") ALT SINIR alınır; tek bir sayı
    saklayabildiğimiz için ortalama uydurmak yerine bilinen bir uç seçilir.
    """
    if not ham:
        return None
    eslesme = re.search(r"\d[\d.]*(?:,\d+)?", ham)
    if not eslesme:
        return None
    metin = eslesme.group(0).replace(".", "").replace(",", ".")
    try:
        deger = float(metin)
    except ValueError:
        return None
    return deger if deger > 0 else None


def tr_tamsayi(ham: Optional[str]) -> Optional[int]:
    """'40.000.000' -> 40000000 (nokta binlik ayracı)."""
    if not ham:
        return None
    temiz = re.sub(r"[^\d]", "", ham)
    return int(temiz) if temiz else None


def _rss_baglantilari(timeout: int = 20) -> List[Dict[str, str]]:
    """RSS'ten (başlık, bağlantı) çiftlerini çeker."""
    try:
        yanit = requests.get(RSS_URL, headers=HEADERS, timeout=timeout)
        yanit.raise_for_status()
        yanit.encoding = "utf-8"
    except Exception as e:
        print(f"[IPO] RSS çekilemedi: {e}")
        return []

    kayitlar = []
    for blok in re.findall(r"<item\b.*?</item>", yanit.text, re.S):
        baslik = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", blok, re.S)
        baglanti = re.search(r"<link>(.*?)</link>", blok, re.S)
        if not baslik or not baglanti:
            continue
        ad = " ".join(html.unescape(baslik.group(1)).split())
        url = baglanti.group(1).strip()
        if ad and url.startswith("http"):
            kayitlar.append({"ad": ad, "url": url})
    return kayitlar


def sayfa_ayristir(hamsayfa: str) -> Dict[str, Any]:
    """Halka arz bilgi sayfasından alanları çıkarır; okunamayan alan None kalır."""
    metin = _duz_metin(hamsayfa)
    sonuc: Dict[str, Any] = {}

    for anahtar, desen in ETIKETLER.items():
        eslesme = re.search(desen, metin)
        if not eslesme:
            sonuc[anahtar] = None
            continue
        # Bazı desenlerde birden çok yakalama grubu var; dolu olanı al.
        deger = next((g for g in eslesme.groups() if g), None)
        sonuc[anahtar] = " ".join(deger.split()) if deger else None

    return {
        "demand_collection_dates": (sonuc.get("tarih") or None),
        "offer_price": tr_para(sonuc.get("fiyat")),
        "lot_distribution_type": (sonuc.get("dagitim") or None),
        "lot_count": tr_tamsayi(sonuc.get("lot")),
        "broker": (sonuc.get("aracikurum") or None),
        "symbol": (sonuc.get("sembol") or None),
        "market": (sonuc.get("pazar") or None),
    }


def halka_arzlari_senkronize_et(db: Session, gecikme_sn: float = 0.6) -> Dict[str, int]:
    """
    RSS'teki halka arzları gezip `ipos` tablosunu günceller.

    Tekilleştirme KAYNAK BAĞLANTISI üzerinden yapılır: şirket adı yazımı
    değişebilir (kısaltma, noktalama), bağlantı sabittir.
    """
    kayitlar = _rss_baglantilari()
    if not kayitlar:
        print("[IPO] RSS boş döndü, senkronizasyon atlandı.")
        return {"gorulen": 0, "yeni": 0, "guncellenen": 0, "atlanan": 0}

    sayac = {"gorulen": len(kayitlar), "yeni": 0, "guncellenen": 0, "atlanan": 0}

    for kayit in kayitlar:
        try:
            yanit = requests.get(kayit["url"], headers=HEADERS, timeout=25)
            yanit.raise_for_status()
            yanit.encoding = "utf-8"
        except Exception as e:
            print(f"[IPO] {kayit['url']} indirilemedi: {e}")
            sayac["atlanan"] += 1
            continue

        alanlar = sayfa_ayristir(yanit.text)

        mevcut = db.query(models.Ipo).filter_by(source_url=kayit["url"]).first()
        if mevcut is None:
            mevcut = models.Ipo(source_url=kayit["url"])
            db.add(mevcut)
            sayac["yeni"] += 1
        else:
            sayac["guncellenen"] += 1

        mevcut.company_name = kayit["ad"][:200]
        mevcut.symbol = alanlar["symbol"]
        mevcut.offer_price = alanlar["offer_price"]
        mevcut.demand_collection_dates = (alanlar["demand_collection_dates"] or "")[:60] or None
        mevcut.lot_distribution_type = (alanlar["lot_distribution_type"] or "")[:50] or None
        mevcut.lot_count = alanlar["lot_count"]
        mevcut.broker = (alanlar["broker"] or "")[:120] or None
        mevcut.market = (alanlar["market"] or "")[:40] or None
        mevcut.updated_at = datetime.utcnow()
        # is_katilim_compliant BİLEREK DOKUNULMAZ — bkz. modül başlığı.

        if gecikme_sn:
            import time
            time.sleep(gecikme_sn)

    db.commit()
    print(f"[IPO] {sayac['gorulen']} arz görüldü, {sayac['yeni']} yeni, "
          f"{sayac['guncellenen']} güncellendi, {sayac['atlanan']} atlandı.")
    return sayac
