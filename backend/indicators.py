"""
indicators.py
-------------
Günlük OHLCV üzerinden ek teknik göstergeler: Stochastic, ADX ve OBV.

NEDEN AYRI BİR MODÜL VE AYRI VERİ KAYNAĞI:
Uygulamadaki mevcut göstergeler (RSI, MACD, SMA, Bollinger) `stock_prices`
tablosundan, yani gün içi anlık fiyat kayıtlarından hesaplanıyor. O tabloda
YALNIZCA fiyat var — yüksek/düşük/açılış yok. Stochastic ve ADX ise tanımı
gereği gün içi yüksek ve düşüğü kullanır; onlarsız hesaplanamazlar (kapanışı
hem yüksek hem düşük saymak göstergeyi anlamsız kılar). Bu yüzden bu üç
gösterge `stock_prices_daily` tablosundaki gerçek OHLCV barlarından üretilir.

GÖSTERGELER
  Stochastic %K/%D — kapanışın son N günün bandındaki yeri. Aşırı alım/satımı
      RSI'dan farklı okur: RSI hızı, Stochastic konumu ölçer.
  ADX             — trendin GÜCÜ (yönü değil). 25 üstü güçlü trend, 20 altı
      yönsüz piyasa demektir. Kesişim stratejileri yönsüz piyasada sürekli
      yanlış sinyal ürettiği için bu gösterge onları filtrelemekte kullanılır.
  OBV             — hacmin yönlü birikimi. Fiyat yükselirken OBV yükselmiyorsa
      hareketin arkasında hacim yok demektir.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

import models


def _stochastic(highs, lows, closes, period: int = 14, smooth: int = 3):
    """%K (yumuşatılmış) ve %D döner."""
    if len(closes) < period + smooth:
        return None, None
    ham = []
    for i in range(period - 1, len(closes)):
        en_yuksek = max(highs[i - period + 1 : i + 1])
        en_dusuk = min(lows[i - period + 1 : i + 1])
        genislik = en_yuksek - en_dusuk
        # Bant sıfır genişlikteyse (tedbir/işlem görmeyen gün) bölme yapılamaz;
        # nötr 50 kabul edilir.
        ham.append(50.0 if genislik == 0 else (closes[i] - en_dusuk) / genislik * 100)
    if len(ham) < smooth:
        return None, None
    k = sum(ham[-smooth:]) / smooth
    if len(ham) < smooth * 2:
        return round(k, 2), None
    d_serisi = [sum(ham[i - smooth + 1 : i + 1]) / smooth for i in range(smooth - 1, len(ham))]
    d = sum(d_serisi[-smooth:]) / smooth
    return round(k, 2), round(d, 2)


def _adx(highs, lows, closes, period: int = 14) -> Optional[float]:
    """Wilder ADX. Trendin gücünü ölçer, yönünü değil."""
    n = len(closes)
    if n < period * 2 + 1:
        return None

    tr, plus_dm, minus_dm = [], [], []
    for i in range(1, n):
        yuksek_fark = highs[i] - highs[i - 1]
        dusuk_fark = lows[i - 1] - lows[i]
        plus_dm.append(yuksek_fark if (yuksek_fark > dusuk_fark and yuksek_fark > 0) else 0.0)
        minus_dm.append(dusuk_fark if (dusuk_fark > yuksek_fark and dusuk_fark > 0) else 0.0)
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))

    def wilder(seri):
        """Wilder yumuşatması: ilk değer toplam, sonrası kademeli."""
        out = [sum(seri[:period])]
        for i in range(period, len(seri)):
            out.append(out[-1] - out[-1] / period + seri[i])
        return out

    tr_s, p_s, m_s = wilder(tr), wilder(plus_dm), wilder(minus_dm)

    dx = []
    for i in range(len(tr_s)):
        if tr_s[i] == 0:
            continue
        pdi = p_s[i] / tr_s[i] * 100
        mdi = m_s[i] / tr_s[i] * 100
        toplam = pdi + mdi
        if toplam == 0:
            continue
        dx.append(abs(pdi - mdi) / toplam * 100)

    if len(dx) < period:
        return None
    adx = sum(dx[:period]) / period
    for i in range(period, len(dx)):
        adx = (adx * (period - 1) + dx[i]) / period
    return round(adx, 2)


def _obv(closes, volumes) -> tuple[Optional[float], Optional[float]]:
    """
    OBV ve son 20 günlük eğimi döner.

    Ham OBV değeri tek başına anlamsızdır (başlangıcı keyfîdir); kullanıcıya
    anlamlı olan YÖNÜDÜR, o yüzden eğim de hesaplanır.
    """
    if len(closes) < 2:
        return None, None
    obv = 0.0
    seri = [0.0]
    for i in range(1, len(closes)):
        hacim = volumes[i] or 0
        if closes[i] > closes[i - 1]:
            obv += hacim
        elif closes[i] < closes[i - 1]:
            obv -= hacim
        seri.append(obv)

    if len(seri) < 21:
        return round(obv, 0), None
    # Eğim: son 20 günün değişiminin, aynı dönemdeki ortalama hacme oranı.
    # Ham fark hisseden hisseye kıyaslanamaz; hacme bölünce normalleşir.
    ort_hacim = sum(v or 0 for v in volumes[-20:]) / 20
    if ort_hacim <= 0:
        return round(obv, 0), None
    egim = (seri[-1] - seri[-21]) / ort_hacim
    return round(obv, 0), round(egim, 2)


def compute_extra_indicators(db: Session, symbol: str) -> dict[str, Any]:
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return {"available": False, "reason": "Hisse bulunamadı."}

    bars = (
        db.query(models.StockPriceDaily)
        .filter_by(stock_id=stock.id)
        .order_by(models.StockPriceDaily.trade_date.desc())
        .limit(200)
        .all()
    )
    bars.reverse()
    if len(bars) < 40:
        return {
            "available": False,
            "reason": "Bu hisse için yeterli günlük geçmiş yok; gece çalışan iş birkaç gün içinde dolduracak.",
        }

    closes = [float(b.close) for b in bars]
    # Yüksek/düşük bazı eski barlarda boş olabilir; o gün kapanışa düşülür.
    highs = [float(b.high) if b.high is not None else float(b.close) for b in bars]
    lows = [float(b.low) if b.low is not None else float(b.close) for b in bars]
    volumes = [int(b.volume) if b.volume is not None else 0 for b in bars]

    k, d = _stochastic(highs, lows, closes)
    adx = _adx(highs, lows, closes)
    obv, obv_egim = _obv(closes, volumes)

    return {
        "available": True,
        "as_of": bars[-1].trade_date,
        "bar_count": len(bars),
        "stochastic_k": k,
        "stochastic_d": d,
        "adx": adx,
        "obv": obv,
        "obv_slope": obv_egim,
    }
