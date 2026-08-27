"""
pivot.py
--------
Klasik Pivot Noktaları (P, R1-R3, S1-S3) ve Fibonacci geri çekilme seviyeleri.

NEDEN YENİDEN YAZILDI (iki ayrı hata vardı)
-------------------------------------------
Eski hali `analysis_engine.calculate_pivot_levels` idi ve KULLANICI İSTEĞİ
SIRASINDA Yahoo Finance'a bağlanıyordu.

1) DIŞ SERVİS BAĞIMLILIĞI. Projenin kendi ilkesi şu: "Uygulama hiçbir dış
   servise kullanıcı isteği sırasında bağlanmaz; tüm dış çağrılar zamanlanmış
   işlerde yapılır." Pivot ucu bu ilkeyi çiğniyordu ve sonucu ölçüldü —
   üretimde uç bir gün içinde çalışır durumdan `available:false`a düştü
   (Yahoo bugünün barını NaN döndürdüğü için), kod hiç değişmeden.

2) YANLIŞ GÜN. Klasik pivot, T günü için T-1 gününün Yüksek/Düşük/Kapanış
   verisinden hesaplanır. Eski kod `history.iloc[-1]` yani SON satırı
   kullanıyordu; seans sonrası son satır BUGÜNDÜR. Yani sonuç, çağrıldığı
   saate göre değişiyordu: bugünün barı henüz oluşmamışsa doğru (dün),
   oluşmuşsa yanlış (bugün) güne göre hesaplanıyordu.

Artık ikisi de kendi `stock_prices_daily` tablomuzdan okunur (188.496 satır,
eksik OHLC sayısı sıfır — ölçüldü). Dış çağrı yok, gün seçimi açık.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

import models
from market_hours import TR_TZ

# Fibonacci aralığı için kaç günlük pencereye bakılır.
FIB_PENCERE_GUN = 20


def _f(deger: Any) -> Optional[float]:
    """Numeric/Decimal -> float; None ve dönüştürülemeyen değer None döner."""
    if deger is None:
        return None
    try:
        sonuc = float(deger)
    except (TypeError, ValueError):
        return None
    # NaN kendine eşit değildir; sessizce hesaba girmesin.
    return None if sonuc != sonuc else sonuc


def hesapla(db: Session, stock_id: int, symbol: str,
            bugun: Optional[date] = None) -> Dict[str, Any]:
    """
    Verilen hisse için pivot ve Fibonacci seviyelerini hesaplar.

    `bugun` yalnızca test için parametredir; üretimde TÜRKİYE tarihi kullanılır.

    NEDEN date.today() DEĞİL: sunucu UTC'de çalışıyor. TSİ 00:00–03:00 arasında
    UTC hâlâ bir önceki gündedir; bu aralıkta `date.today()` dünü döndürür,
    kapanmış olan son seans "bugün" sayılıp elenir ve pivot BİR GÜN BAYAT
    çıkar. Ölçüldü: TSİ 01:54'te üretim 26 Ağustos barını kullanırken yerel
    makine (TSİ) 27 Ağustos barını kullanıyordu — aynı kod, farklı sonuç.
    Piyasa Türkiye'de olduğu için gün sınırı da Türkiye saatiyle belirlenir.
    """
    bugun = bugun or datetime.now(TR_TZ).date()

    # BUGÜN HARİÇ tutulur: klasik pivot bir ÖNCEKİ tam işlem gününe dayanır.
    # Bugünün barı seans sürerken yarımdır, seans sonrası da "önceki gün"
    # değildir.
    barlar: List[models.StockPriceDaily] = (
        db.query(models.StockPriceDaily)
        .filter(models.StockPriceDaily.stock_id == stock_id,
                models.StockPriceDaily.trade_date < bugun)
        .order_by(models.StockPriceDaily.trade_date.desc())
        .limit(FIB_PENCERE_GUN)
        .all()
    )

    if not barlar:
        return {
            "symbol": symbol.upper(),
            "available": False,
            "message": "Pivot seviyeleri için günlük fiyat verisi bulunamadı.",
        }

    onceki = barlar[0]
    yuksek, dusuk, kapanis = _f(onceki.high), _f(onceki.low), _f(onceki.close)
    if yuksek is None or dusuk is None or kapanis is None:
        return {
            "symbol": symbol.upper(),
            "available": False,
            "message": "Pivot seviyeleri için geçerli Yüksek/Düşük/Kapanış verisi bulunamadı.",
        }

    pivot = round((yuksek + dusuk + kapanis) / 3, 2)
    aralik = yuksek - dusuk
    r1 = round((2 * pivot) - dusuk, 2)
    s1 = round((2 * pivot) - yuksek, 2)
    r2 = round(pivot + aralik, 2)
    s2 = round(pivot - aralik, 2)
    r3 = round(yuksek + 2 * (pivot - dusuk), 2)
    s3 = round(dusuk - 2 * (yuksek - pivot), 2)

    # Fibonacci: son 20 işlem gününün en yüksek/en düşük aralığı.
    yuksekler = [y for y in (_f(b.high) for b in barlar) if y is not None]
    dusukler = [d for d in (_f(b.low) for b in barlar) if d is not None]
    fib_236 = fib_382 = fib_500 = fib_618 = None
    if yuksekler and dusukler:
        tepe, dip = max(yuksekler), min(dusukler)
        if tepe > dip:
            fark = tepe - dip
            fib_236 = round(tepe - fark * 0.236, 2)
            fib_382 = round(tepe - fark * 0.382, 2)
            fib_500 = round(tepe - fark * 0.500, 2)
            fib_618 = round(tepe - fark * 0.618, 2)

    return {
        "symbol": symbol.upper(),
        "as_of_date": onceki.trade_date.isoformat(),
        "previous_close": kapanis,
        "pivot": pivot,
        "r1": r1, "r2": r2, "r3": r3,
        "s1": s1, "s2": s2, "s3": s3,
        "fib_236": fib_236, "fib_382": fib_382, "fib_500": fib_500, "fib_618": fib_618,
        "available": True,
        "message": None,
    }
