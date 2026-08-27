"""
seasonality.py
----------------
Aylık mevsimsellik: "Bu hisse tarihsel olarak Ocak'ta nasıl davranıyor?"

Ücretli terminallerde "mevsimsellik" veya "geçmiş performans deseni" adıyla
satılan bir analiz. Tamamen `stock_prices_daily` tablosundaki günlük
kapanışlardan hesaplanır, ek veri kaynağı gerekmez.

YÖNTEM: her (yıl, ay) çifti için o ay içindeki İLK ve SON kapanış arasındaki
getiri hesaplanır. Ay sonundan ay sonuna (chained) yerine ay İÇİNDE ilk/son
kullanılmasının sebebi: bir yılda o ay hiç veri yoksa (örn. hisse o tarihte
henüz halka açılmamışsa) zincirleme yöntem bir sonraki ayı da bozardı; bu
yöntemde her ay bağımsız değerlendirilir.

DÜRÜSTLÜK SINIRI: bu bir TAHMİN ARACI DEĞİLDİR. Geçmişte bir ayın sık
yükselmiş olması gelecekte de yükseleceği anlamına gelmez — az örnekli
(genelde 5 yıl = 5 gözlem) bir istatistik kolayca tesadüf olabilir. Bu uyarı
API yanıtında ve arayüzde AÇIKÇA yer alır.
"""

from collections import defaultdict
from typing import Dict, List, Optional, TypedDict

from sqlalchemy.orm import Session

import models

AY_ADLARI = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]

MIN_YEARS_REQUIRED = 3  # daha azında "desen" demek istatistiksel olarak anlamsız


class MonthSeasonality(TypedDict):
    month: int
    month_name: str
    years_observed: int
    avg_return_pct: float
    positive_year_ratio: float   # 0.0-1.0: kaç yılın kaçında o ay pozitifti


def compute_seasonality(db: Session, stock_id: int) -> Optional[List[MonthSeasonality]]:
    """
    None döner: yeterli tarihsel veri yoksa (yeni hisse, kısa geçmiş).
    Sessizce eksik/yanıltıcı bir desen göstermek yerine özellik gizlenir.
    """
    rows = (
        db.query(models.StockPriceDaily.trade_date, models.StockPriceDaily.close)
        .filter(
            models.StockPriceDaily.stock_id == stock_id,
            models.StockPriceDaily.close.isnot(None),
        )
        .order_by(models.StockPriceDaily.trade_date.asc())
        .all()
    )
    if not rows:
        return None

    # (yıl, ay) -> [kapanışlar, tarih sırasına göre]
    by_month: Dict[tuple, List[float]] = defaultdict(list)
    for trade_date, close in rows:
        by_month[(trade_date.year, trade_date.month)].append(float(close))

    # Her ay numarası (1-12) için, o ayın gözlemlendiği YILLARDAKİ getiriler
    returns_by_month_num: Dict[int, List[float]] = defaultdict(list)
    for (yil, ay), kapaniclar in by_month.items():
        if len(kapaniclar) < 2 or kapaniclar[0] <= 0:
            continue  # tek günlük veri veya bozuk kapanış -> güvenilmez
        getiri = (kapaniclar[-1] / kapaniclar[0] - 1) * 100
        returns_by_month_num[ay].append(getiri)

    sonuc: List[MonthSeasonality] = []
    for ay in range(1, 13):
        gozlemler = returns_by_month_num.get(ay, [])
        if len(gozlemler) < MIN_YEARS_REQUIRED:
            continue
        pozitif_oran = sum(1 for g in gozlemler if g > 0) / len(gozlemler)
        sonuc.append(MonthSeasonality(
            month=ay,
            month_name=AY_ADLARI[ay - 1],
            years_observed=len(gozlemler),
            avg_return_pct=round(sum(gozlemler) / len(gozlemler), 2),
            positive_year_ratio=round(pozitif_oran, 3),
        ))

    return sonuc if sonuc else None
