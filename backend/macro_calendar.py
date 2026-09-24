"""
macro_calendar.py
-----------------
Ekonomik takvim: BİST'i etkileyebilecek makro veri açıklamaları ve borsa tatilleri.

VERİ KAYNAĞI: dış bir API YOK (ücretsiz ve kararlı bir makro takvim API'si
bulunmuyor, scrape etmek de kırılgan). Tarihler KURALLARLA üretilir -- örneğin
TÜİK enflasyonu her ayın 3'ünde (hafta sonu/tatile denk gelirse sonraki iş günü)
açıklar. Kesin kuralı olmayan olaylar (işsizlik, cari denge, ABD verileri)
`tahmini=True` ile işaretlenir ve arayüzde "tahmini" rozetiyle gösterilir; resmi
takvim her zaman esas alınmalıdır. Açıklama metinleri kural tabanlıdır (LLM yok).

KASITLI OLARAK YOK: faiz kararı satırları (TCMB PPK, Fed faiz kararı). Uygulama
katılım (faizsiz) ilkesine göre tasarlandı -- bkz. proje-özellikleri.md.

Borsa tatilleri market_hours.BIST_HOLIDAYS'ten gelir; o liste yılda bir elle
güncellenir (şu an 2026 sonuna kadar).
"""

from datetime import date, timedelta
from typing import List, TypedDict

from market_hours import BIST_HOLIDAYS


class MakroEtkinlik(TypedDict):
    tarih: date
    baslik: str
    kategori: str          # 'TURKIYE' | 'ABD' | 'TATIL'
    onem: int              # 1 (düşük) - 3 (yüksek)
    tahmini: bool
    aciklama: str


def _is_gunu_mu(d: date, tatilleri_atla: bool) -> bool:
    if d.weekday() >= 5:
        return False
    return not (tatilleri_atla and d in BIST_HOLIDAYS)


def _sonraki_is_gunu(d: date, tatilleri_atla: bool) -> date:
    while not _is_gunu_mu(d, tatilleri_atla):
        d += timedelta(days=1)
    return d


def _ilk_cuma(yil: int, ay: int) -> date:
    d = date(yil, ay, 1)
    while d.weekday() != 4:
        d += timedelta(days=1)
    return d


# (baslik, kategori, gun, onem, tahmini, aciklama, yalnizca_aylar|None)
# gun: ayın günü; "ILK_CUMA" özel değer.
_KURALLAR = [
    ("TÜFE (Enflasyon)", "TURKIYE", 3, 3, False,
     "TÜİK bir önceki ayın enflasyonunu açıklar. Beklentiden yüksek gelmesi genelde "
     "alım gücü ve maliyet baskısı endişesiyle bankacılık ve perakende hisselerinde "
     "oynaklık yaratır; düşük gelmesi ise genelde piyasada olumlu karşılanır.",
     None),
    ("Dış Ticaret (öncü veri)", "TURKIYE", 4, 2, True,
     "İhracat ve ithalat rakamlarının öncü verisi. İhracatçı şirketler (sanayi, "
     "otomotiv, beyaz eşya) ve dış ticaret açığı takip eden yatırımcılar için önemlidir.",
     None),
    ("İşsizlik ve Sanayi Üretimi", "TURKIYE", 10, 2, True,
     "İşgücü ve sanayi üretimi verileri ekonomik büyümenin yönüne dair ipucu verir. "
     "Güçlü üretim verisi genelde sanayi ve holding hisseleri için olumlu okunur.",
     None),
    ("Cari İşlemler Dengesi", "TURKIYE", 11, 2, True,
     "TCMB, ülkenin dış finansman ihtiyacını gösteren cari dengeyi açıklar. Açığın "
     "büyümesi kur ve dış borçlanma riskiyle ilişkilendirildiği için piyasayı etkileyebilir.",
     None),
    ("GSYH (Büyüme)", "TURKIYE", 1, 3, True,
     "Çeyreklik ekonomik büyüme rakamı. Beklentinin üzerinde büyüme genelde geniş "
     "tabanlı bir hisse yükselişine, zayıf büyüme ise temkine yol açabilir.",
     (3, 6, 9, 12)),
    ("ABD Tarım Dışı İstihdam (NFP)", "ABD", "ILK_CUMA", 3, True,
     "ABD işgücü piyasası verisi küresel risk iştahını etkiler. Gelişmekte olan "
     "piyasalar olan BİST de küresel fon akışlarına duyarlıdır.",
     None),
    ("ABD TÜFE (Enflasyon)", "ABD", 12, 3, True,
     "ABD enflasyonu küresel para politikası beklentilerini şekillendirir; sonuçları "
     "dolar ve gelişmekte olan piyasa hisseleri üzerinde kısa vadeli hareket yaratabilir.",
     None),
]


def _tatil_bloklari() -> List[List[date]]:
    """Ardışık tatil günlerini tek blokta toplar (Bayram = 1 satır)."""
    blok: List[List[date]] = []
    for g in sorted(BIST_HOLIDAYS):
        if blok and (g - blok[-1][-1]).days == 1:
            blok[-1].append(g)
        else:
            blok.append([g])
    return blok


def etkinlikler(baslangic: date, gun: int) -> List[MakroEtkinlik]:
    """[baslangic, baslangic+gun] aralığındaki etkinlikler, tarihe göre sıralı."""
    bitis = baslangic + timedelta(days=gun)
    sonuc: List[MakroEtkinlik] = []

    # Aralığı kapsayan aylar (+ önceki ay: tatilde öteye kayan açıklamalar için).
    yil, ay = baslangic.year, baslangic.month
    aylar = []
    while (yil, ay) <= (bitis.year, bitis.month):
        aylar.append((yil, ay))
        ay += 1
        if ay == 13:
            yil, ay = yil + 1, 1

    for (y, m) in aylar:
        for baslik, kategori, gun_kural, onem, tahmini, aciklama, aylar_kisit in _KURALLAR:
            if aylar_kisit and m not in aylar_kisit:
                continue
            if gun_kural == "ILK_CUMA":
                d = _ilk_cuma(y, m)
            else:
                d = date(y, m, gun_kural)
            d = _sonraki_is_gunu(d, tatilleri_atla=(kategori == "TURKIYE"))
            if baslangic <= d <= bitis:
                sonuc.append({"tarih": d, "baslik": baslik, "kategori": kategori,
                              "onem": onem, "tahmini": tahmini, "aciklama": aciklama})

    for blok in _tatil_bloklari():
        ilk, son = blok[0], blok[-1]
        if son < baslangic or ilk > bitis:
            continue
        aralik = (f"{ilk.day}.{ilk.month:02d}" if ilk == son
                  else f"{ilk.day}.{ilk.month:02d} - {son.day}.{son.month:02d}")
        sonuc.append({
            "tarih": max(ilk, baslangic), "baslik": "Borsa tatili", "kategori": "TATIL",
            "onem": 2, "tahmini": False,
            "aciklama": f"Borsa İstanbul {aralik} tarihlerinde resmi tatil nedeniyle kapalı "
                        f"({len(blok)} gün). Bu günlerde alım-satım yapılamaz.",
        })

    sonuc.sort(key=lambda e: (e["tarih"], -e["onem"]))
    return sonuc
