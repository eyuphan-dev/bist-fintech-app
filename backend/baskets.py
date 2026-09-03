"""
baskets.py
----------
Tematik sepetler: "tek tıkla" yatırım yapılabilen, küratörlü hisse grupları.

Yeni bir veri kaynağı GEREKTİRMEZ -- zaten var olan katılım durumu, temettü
geçmişi, Piotroski F-Skoru ve piyasa değeri verisini yeniden paketler. Her
sepetin üyeleri, tanımdaki SQL filtresine göre HER İSTEKTE canlı hesaplanır
(ayrı bir "sepet üyeliği" tablosu tutulmaz) -- böylece veri güncellendiğinde
(ör. bir hissenin katılım durumu değişince) sepet içeriği otomatik güncel
kalır, elle senkronize edilmesi gereken ikinci bir kayıt olmaz.
"""

from typing import Any, Dict, List, Optional, TypedDict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import models

SEPET_BOYUTU = 10


class SepetTanimi(TypedDict):
    id: str
    isim: str
    aciklama: str


BASKET_TANIMLARI: List[SepetTanimi] = [
    {
        "id": "temettu-krallari",
        "isim": "Temettü Kralları",
        "aciklama": "En az 3 yıldır düzenli temettü ödeyen, verimi en yüksek 10 hisse.",
    },
    {
        "id": "katilim-uyumlu",
        "isim": "Katılım Uyumlu Sepet",
        "aciklama": "KAP'a göre faizsiz yatırım ilkelerine uygun, piyasa değeri en yüksek 10 hisse.",
    },
    {
        "id": "saglam-bilanco",
        "isim": "Sağlam Bilanço Sepeti",
        "aciklama": "Piotroski F-Skoru 7 ve üzeri, mali açıdan en güçlü 10 şirket.",
    },
    {
        "id": "buyuk-sermaye",
        "isim": "Büyük Sermaye Sepeti",
        "aciklama": "BIST'te piyasa değeri en yüksek 10 hisse.",
    },
]

_TANIM_HARITASI = {t["id"]: t for t in BASKET_TANIMLARI}


def sepet_tanimlari() -> List[SepetTanimi]:
    return BASKET_TANIMLARI


def _temettu_krallari(db: Session) -> List[models.Stock]:
    # En az 3 farklı yılda ödeme yapmış hisseler (gerçek istikrar sinyali;
    # tek seferlik yüksek verim listeye giremesin).
    # extract('year', ...) hem PostgreSQL'de hem SQLite'ta (CI) calisir --
    # strftime yalnizca SQLite'a ozgudur, uretimde patlardi.
    yil = func.extract("year", models.DividendHistory.pay_date)
    yeterli_gecmisi_olanlar = (
        select(models.DividendHistory.stock_id)
        .group_by(models.DividendHistory.stock_id)
        .having(func.count(func.distinct(yil)) >= 3)
    )
    return (
        db.query(models.Stock)
        .join(models.CompanyAnalysis, models.CompanyAnalysis.stock_id == models.Stock.id)
        .filter(models.Stock.id.in_(yeterli_gecmisi_olanlar))
        .filter(models.CompanyAnalysis.dividend_yield.isnot(None))
        .filter(models.CompanyAnalysis.dividend_yield > 0)
        .order_by(models.CompanyAnalysis.dividend_yield.desc())
        .limit(SEPET_BOYUTU)
        .all()
    )


def _katilim_uyumlu(db: Session) -> List[models.Stock]:
    return (
        db.query(models.Stock)
        .outerjoin(models.CompanyAnalysis, models.CompanyAnalysis.stock_id == models.Stock.id)
        .filter(models.Stock.katilim_status == "UYGUN")
        .order_by(models.CompanyAnalysis.market_cap.desc().nullslast())
        .limit(SEPET_BOYUTU)
        .all()
    )


def _saglam_bilanco(db: Session) -> List[models.Stock]:
    return (
        db.query(models.Stock)
        .join(models.CompanyAnalysis, models.CompanyAnalysis.stock_id == models.Stock.id)
        .filter(models.CompanyAnalysis.piotroski_score.isnot(None))
        .filter(models.CompanyAnalysis.piotroski_score >= 7)
        .order_by(models.CompanyAnalysis.piotroski_score.desc())
        .limit(SEPET_BOYUTU)
        .all()
    )


def _buyuk_sermaye(db: Session) -> List[models.Stock]:
    return (
        db.query(models.Stock)
        .join(models.CompanyAnalysis, models.CompanyAnalysis.stock_id == models.Stock.id)
        .filter(models.CompanyAnalysis.market_cap.isnot(None))
        .order_by(models.CompanyAnalysis.market_cap.desc())
        .limit(SEPET_BOYUTU)
        .all()
    )


_SORGULAR = {
    "temettu-krallari": _temettu_krallari,
    "katilim-uyumlu": _katilim_uyumlu,
    "saglam-bilanco": _saglam_bilanco,
    "buyuk-sermaye": _buyuk_sermaye,
}


def sepet_hisseleri(db: Session, basket_id: str) -> Optional[List[models.Stock]]:
    """basket_id geçersizse None döner (main.py 404 üretir)."""
    sorgu = _SORGULAR.get(basket_id)
    if sorgu is None:
        return None
    return sorgu(db)


def sepet_tanimi(basket_id: str) -> Optional[SepetTanimi]:
    return _TANIM_HARITASI.get(basket_id)
