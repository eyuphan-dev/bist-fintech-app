"""
veri_sagligi.py
---------------
Her veri boru hattının TAZE olup olmadığını tek bakışta raporlar.

NEDEN VAR
---------
Bu uygulamanın arızalarının çoğu "kod patladı" değil, "veri sessizce
gelmiyor" biçiminde. Ölçüldü — bir gecelik denetimde bulunanlar:

  • Önemli pay sahibi haber akışı aylardır 0 kayıt döndürüyordu.
  • Fon kataloğu 3 fonda takılı kalmıştı (TEFAS 2.470 fon veriyordu).
  • Halka arz tablosunu dolduran hiçbir kod yoktu, tablo hep boştu.
  • Hisse haberlerinin en yenisi 5 gün eskiydi.
  • KAP istek sınırı aşılınca bir turdaki 36 formun tamamı sessizce
    kayboluyordu.

Bunların HİÇBİRİ hata logu üretmiyordu; hepsi 200 dönen, boş yanıtlardı.
Elle kazmadan fark edilmiyorlardı. Bu modül o kazma işini kalıcı hale
getirir: her boru hattının son kayıt tarihine ve satır sayısına bakar,
beklenen tazelik penceresini aşanı "BAYAT" olarak işaretler.

TASARIM: EŞİKLER VERİYE GÖRE, TAHMİNE GÖRE DEĞİL
------------------------------------------------
Her hattın tazelik eşiği, onu besleyen işin ÇALIŞMA SIKLIĞINDAN türetilir
(bkz. scheduler.py). Günde bir çalışan bir iş için 2 günlük pencere,
tek bir başarısız turda alarm çalmasını önler ama iki gün üst üste
başarısızlığı yakalar.

BU UÇ GİZLİ VERİ SIZDIRMAZ: yalnızca satır sayısı ve tarih döner,
kullanıcı bilgisi ya da içerik dönmez.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

import models

# (anahtar, görünen ad, model, tarih kolonu, azami yaş SAAT, asgari satır)
#
# Azami yaş, besleyen işin sıklığından türetilir:
#   - 15 dakikada bir çalışan kur işi          -> 2 saat
#   - hafta içi 5 dakikada bir çalışan fiyat   -> 96 saat (uzun hafta sonu + tatil)
#   - günde bir çalışan işler                  -> 48 saat
KONTROLLER = [
    ("fiyat_tik", "Hisse fiyat tikleri", models.StockPrice, "recorded_at", 96, 100),
    ("gunluk_bar", "Günlük OHLCV barları", models.StockPriceDaily, "trade_date", 96, 1000),
    ("kap", "KAP bildirimleri", models.KapNotification, "publish_date", 48, 10),
    ("piyasa_haber", "Türkçe piyasa haberleri", models.MarketNews, "published_at", 48, 20),
    ("fon_fiyat", "TEFAS fon fiyatları", models.FundPrice, "recorded_date", 96, 20),
    ("temettu_olay", "Temettü takvimi", models.DividendEvent, "payment_date", None, 1),
    ("halka_arz", "Halka arz takvimi", models.Ipo, "updated_at", 48, 1),
    ("analiz", "Şirket analizleri", models.CompanyAnalysis, "updated_at", 72, 50),
]


# Döviz/altın kuru ayrı bir tabloda değil, IndexHistory içinde sembol
# bazında tutuluyor (bkz. models.IndexHistory ve tr_market.py). Bu yüzden
# genel kontrol listesine sığmıyor, kendi kontrolü var.
KUR_SEMBOLLERI = ("USDTRY", "EURTRY", "GRAMALTIN")
KUR_AZAMI_SAAT = 2  # 15 dakikada bir tazelenir; 2 saat rahat bir pencere


def _kur_kontrolu(db: Session, simdi: datetime) -> Dict[str, Any]:
    """Kur/altın satırının tazeliği. updated_at kullanılır — trade_date yalnızca
    günü verir, oysa bu değerler gün içinde 15 dakikada bir güncelleniyor."""
    en_yeni = (
        db.query(func.max(models.IndexHistory.updated_at))
        .filter(models.IndexHistory.symbol.in_(KUR_SEMBOLLERI))
        .scalar()
    )
    adet = (
        db.query(func.count(models.IndexHistory.id))
        .filter(models.IndexHistory.symbol.in_(KUR_SEMBOLLERI))
        .scalar()
    ) or 0

    yas = round((simdi - en_yeni).total_seconds() / 3600, 1) if en_yeni else None
    durum, mesaj = "TAMAM", None
    if adet == 0 or en_yeni is None:
        durum, mesaj = "BOS", "hiç kayıt yok"
    elif yas is not None and yas > KUR_AZAMI_SAAT:
        durum, mesaj = "BAYAT", f"son güncelleme {yas} saat önce (azami {KUR_AZAMI_SAAT} saat)"

    return {
        "anahtar": "kur_altin", "ad": "Dolar/Euro/Gram altın", "durum": durum,
        "adet": adet, "en_yeni": en_yeni.isoformat() if en_yeni else None,
        "yas_saat": yas, "mesaj": mesaj,
    }


def _en_yeni(db: Session, model, kolon_adi: str) -> Optional[datetime]:
    kolon = getattr(model, kolon_adi, None)
    if kolon is None:
        return None
    deger = db.query(func.max(kolon)).scalar()
    if deger is None:
        return None
    # trade_date/recorded_date gibi alanlar `date`; karşılaştırma için
    # datetime'a yükseltilir.
    if isinstance(deger, date) and not isinstance(deger, datetime):
        return datetime.combine(deger, datetime.min.time())
    return deger


def rapor(db: Session) -> Dict[str, Any]:
    """Tüm boru hatlarının sağlık raporunu döner."""
    simdi = datetime.utcnow()
    satirlar: List[Dict[str, Any]] = []
    bayat_sayisi = 0
    bos_sayisi = 0

    kur = _kur_kontrolu(db, simdi)
    satirlar.append(kur)
    if kur["durum"] == "BAYAT":
        bayat_sayisi += 1
    elif kur["durum"] == "BOS":
        bos_sayisi += 1

    for anahtar, ad, model, kolon, azami_saat, asgari_satir in KONTROLLER:
        try:
            adet = db.query(func.count(model.id)).scalar() or 0
            en_yeni = _en_yeni(db, model, kolon)
        except Exception as e:
            satirlar.append({
                "anahtar": anahtar, "ad": ad, "durum": "HATA",
                "adet": None, "en_yeni": None, "yas_saat": None,
                "mesaj": str(e)[:120],
            })
            continue

        yas_saat = None
        if en_yeni is not None:
            yas_saat = round((simdi - en_yeni).total_seconds() / 3600, 1)

        durum = "TAMAM"
        mesaj = None
        if adet < asgari_satir:
            durum = "BOS"
            mesaj = f"{adet} satır (en az {asgari_satir} bekleniyor)"
            bos_sayisi += 1
        elif azami_saat is not None and yas_saat is not None and yas_saat > azami_saat:
            durum = "BAYAT"
            mesaj = f"son kayıt {yas_saat} saat önce (azami {azami_saat} saat)"
            bayat_sayisi += 1
        elif azami_saat is not None and en_yeni is None:
            durum = "BOS"
            mesaj = "hiç kayıt yok"
            bos_sayisi += 1

        satirlar.append({
            "anahtar": anahtar,
            "ad": ad,
            "durum": durum,
            "adet": adet,
            # Gelecek tarihli kayıtlarda (temettü ödeme planı) yaş negatif
            # olur; bu bir hata değil, o yüzden eşik uygulanmıyor.
            "en_yeni": en_yeni.isoformat() if en_yeni else None,
            "yas_saat": yas_saat,
            "mesaj": mesaj,
        })

    # Genel durum EN KÖTÜ satıra göre belirlenir; "çoğu iyi" demek,
    # sessizce boş kalan tek bir hattı gizlerdi.
    genel = "TAMAM"
    if any(s["durum"] == "HATA" for s in satirlar):
        genel = "HATA"
    elif bos_sayisi:
        genel = "BOS"
    elif bayat_sayisi:
        genel = "BAYAT"

    return {
        "durum": genel,
        "kontrol_edildi": simdi.isoformat(),
        "bayat_sayisi": bayat_sayisi,
        "bos_sayisi": bos_sayisi,
        "hatlar": satirlar,
    }
