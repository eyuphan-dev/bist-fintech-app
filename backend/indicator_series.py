"""
indicator_series.py
--------------------
Fiyat grafiğinin üstüne bindirilecek (SMA/EMA/Bollinger) ve altına panel
olarak eklenecek (RSI/MACD/Stochastic/ADX/OBV) göstergelerin TAM ZAMAN
SERİSİNİ döner — TradingView/Midas'taki "gösterge ekle" özelliğinin
karşılığı.

NEDEN AYRI BİR MODÜL VE NEDEN MATEMATİK TEKRAR YAZILMADI:
RSI/SMA/EMA/MACD serilerinin Wilder/EMA matematiği zaten backtest.py'de
(_rsi_serisi, _sma_serisi, _ema_serisi, _macd_serisi) doğrulanmış durumda —
geri test sonuçları bu seriler üzerine kurulu. Burada aynı matematiği ikinci
kez yazmak, iki farklı yuvarlama/başlangıç noktası yüzünden grafikte ve
backtest raporunda FARKLI RSI değerleri göstermek riski taşırdı. Bu yüzden
doğrudan import edilir.

Aynı gerekçeyle Stochastic/ADX/OBV'nin matematiği indicators.py'deki
(_stochastic, _adx, _obv) SON DEĞER hesaplarıyla birebir aynı olacak şekilde
yazıldı — ExtraIndicatorsPanel'de gösterilen "güncel" değer ile buradaki
serinin son noktası aynı sayıyı vermeli, aksi halde aynı sayfada iki farklı
ADX görünür.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import threading
import time

from sqlalchemy.orm import Session

import models
from constants import HISTORY_RANGE_DAYS
from backtest import _rsi_serisi, _sma_serisi, _ema_serisi, _macd_serisi

# Tarama/gösterge serisi hesaplaması ölçüldü (~45ms / 1275 bar, tüm seriler
# birden) ama bir hisse sayfası açıkken kullanıcı aralık/gösterge değiştirdikçe
# tekrar tekrar istek atar. signals.py'deki desenle aynı: kısa TTL'li önbellek.
_CACHE_TTL_SECONDS = 300
_cache_lock = threading.Lock()
_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}


def _bollinger_serisi(closes: List[float], period: int = 20, mult: float = 2.0):
    """Orta bant SMA, üst/alt bant ± mult*standart sapma."""
    n = len(closes)
    ust: List[Optional[float]] = [None] * n
    orta: List[Optional[float]] = [None] * n
    alt: List[Optional[float]] = [None] * n
    for i in range(period - 1, n):
        pencere = closes[i - period + 1 : i + 1]
        ort = sum(pencere) / period
        varyans = sum((x - ort) ** 2 for x in pencere) / period
        sapma = varyans ** 0.5
        orta[i] = ort
        ust[i] = ort + mult * sapma
        alt[i] = ort - mult * sapma
    return ust, orta, alt


def _stochastic_serisi(highs: List[float], lows: List[float], closes: List[float], period: int = 14, smooth: int = 3):
    """indicators.py:_stochastic ile aynı matematik, TAM SERİ olarak."""
    n = len(closes)
    k_serisi: List[Optional[float]] = [None] * n
    for i in range(period - 1, n):
        en_yuksek = max(highs[i - period + 1 : i + 1])
        en_dusuk = min(lows[i - period + 1 : i + 1])
        genislik = en_yuksek - en_dusuk
        ham = 50.0 if genislik == 0 else (closes[i] - en_dusuk) / genislik * 100
        k_serisi[i] = ham

    # NOT: K, yuvarlanmadan ÖNCE D'nin girdisi olarak kullanılır -- referans
    # (indicators.py:_stochastic) da öyle yapıyor. Ara adımda yuvarlarsak son
    # basamakta gauge panelindeki değerden sapar (ölçüldü: 64.43 yerine 64.42).
    k_ham: List[Optional[float]] = [None] * n
    ham_degerler = [(i, v) for i, v in enumerate(k_serisi) if v is not None]
    for idx in range(smooth - 1, len(ham_degerler)):
        pencere = [v for _, v in ham_degerler[idx - smooth + 1 : idx + 1]]
        k_ham[ham_degerler[idx][0]] = sum(pencere) / smooth

    d_ham: List[Optional[float]] = [None] * n
    k_gecerli = [(i, v) for i, v in enumerate(k_ham) if v is not None]
    for idx in range(smooth - 1, len(k_gecerli)):
        pencere = [v for _, v in k_gecerli[idx - smooth + 1 : idx + 1]]
        d_ham[k_gecerli[idx][0]] = sum(pencere) / smooth

    k_yumusatilmis = [round(v, 2) if v is not None else None for v in k_ham]
    d_serisi = [round(v, 2) if v is not None else None for v in d_ham]
    return k_yumusatilmis, d_serisi


def _adx_serisi(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> List[Optional[float]]:
    """indicators.py:_adx ile aynı Wilder matematiği, TAM SERİ olarak."""
    n = len(closes)
    out: List[Optional[float]] = [None] * n
    if n < period * 2 + 1:
        return out

    tr, plus_dm, minus_dm = [], [], []
    for i in range(1, n):
        yuksek_fark = highs[i] - highs[i - 1]
        dusuk_fark = lows[i - 1] - lows[i]
        plus_dm.append(yuksek_fark if (yuksek_fark > dusuk_fark and yuksek_fark > 0) else 0.0)
        minus_dm.append(dusuk_fark if (dusuk_fark > yuksek_fark and dusuk_fark > 0) else 0.0)
        tr.append(max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])))

    def wilder(seri):
        out_ = [sum(seri[:period])]
        for i in range(period, len(seri)):
            out_.append(out_[-1] - out_[-1] / period + seri[i])
        return out_

    tr_s, p_s, m_s = wilder(tr), wilder(plus_dm), wilder(minus_dm)

    dx: List[float] = []
    dx_index: List[int] = []  # tr_s/p_s/m_s dizinindeki karşılığı
    for i in range(len(tr_s)):
        if tr_s[i] == 0:
            continue
        pdi = p_s[i] / tr_s[i] * 100
        mdi = m_s[i] / tr_s[i] * 100
        toplam = pdi + mdi
        if toplam == 0:
            continue
        dx.append(abs(pdi - mdi) / toplam * 100)
        dx_index.append(i)

    if len(dx) < period:
        return out

    # tr_s[m], closes dizisinde (period + m) konumuna karşılık gelir: wilder()
    # ilk değeri tr[0..period-1]'in toplamıdır ve tr[j], closes[j+1]'den
    # türetilir (bkz. döngü: `for i in range(1, n)`), yani tr_s[0] ~ closes[period].
    # dx_index[j] ise dx[j]'nin tr_s dizinindeki konumudur (0 TR atlanmadıysa m ile
    # aynı) -- bu yüzden dx[j]'nin closes karşılığı (period + dx_index[j]) olur.
    adx = sum(dx[:period]) / period
    out[period + dx_index[period - 1]] = round(adx, 2)
    for i in range(period, len(dx)):
        adx = (adx * (period - 1) + dx[i]) / period
        out[period + dx_index[i]] = round(adx, 2)
    return out


def _obv_serisi(closes: List[float], volumes: List[float]) -> List[Optional[float]]:
    """indicators.py:_obv ile aynı matematik, TAM SERİ olarak (eğim hariç)."""
    n = len(closes)
    out: List[Optional[float]] = [None] * n
    if n < 2:
        return out
    obv = 0.0
    out[0] = 0.0
    for i in range(1, n):
        hacim = volumes[i] or 0
        if closes[i] > closes[i - 1]:
            obv += hacim
        elif closes[i] < closes[i - 1]:
            obv -= hacim
        out[i] = round(obv, 0)
    return out


def compute_indicator_series(db: Session, symbol: str, range_code: str) -> Dict[str, Any]:
    range_code = (range_code or "").upper()
    if range_code == "1D" or range_code not in HISTORY_RANGE_DAYS:
        return {
            "available": False,
            "reason": "Göstergeler yalnızca günlük barlı aralıklarda (1H/1A/1Y/5Y) hesaplanır.",
        }

    cache_key = f"{symbol.upper()}:{range_code}"
    now = time.time()
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return {"available": False, "reason": "Hisse bulunamadı."}

    cutoff = date.today() - timedelta(days=HISTORY_RANGE_DAYS[range_code])
    # Göstergelerin ısınma payı (SMA200 gibi) olması için aralığın öncesinden
    # de bar çekilir, sonra yalnızca istenen aralığa kırpılır -- aksi halde
    # "1Y" seçiliyken SMA200 grafiğin ilk ~200 günü boyunca hiç çizilmezdi.
    isinma_gun = 260
    bars = (
        db.query(models.StockPriceDaily)
        .filter(models.StockPriceDaily.stock_id == stock.id)
        .order_by(models.StockPriceDaily.trade_date.asc())
        .all()
    )
    if len(bars) < 30:
        return {"available": False, "reason": "Bu hisse için yeterli günlük geçmiş yok."}

    kirpma_index = 0
    for i, b in enumerate(bars):
        if b.trade_date >= cutoff:
            kirpma_index = max(0, i - isinma_gun)
            break

    hesap_bars = bars[kirpma_index:]
    closes = [float(b.close) for b in hesap_bars]
    highs = [float(b.high) if b.high is not None else float(b.close) for b in hesap_bars]
    lows = [float(b.low) if b.low is not None else float(b.close) for b in hesap_bars]
    volumes = [float(b.volume) if b.volume is not None else 0.0 for b in hesap_bars]
    dates = [b.trade_date for b in hesap_bars]

    sma20 = _sma_serisi(closes, 20)
    sma50 = _sma_serisi(closes, 50)
    sma200 = _sma_serisi(closes, 200)
    ema20 = _ema_serisi(closes, 20)
    bb_ust, bb_orta, bb_alt = _bollinger_serisi(closes, 20, 2.0)
    rsi14 = _rsi_serisi(closes, 14)
    macd, macd_sinyal = _macd_serisi(closes, 12, 26, 9)
    macd_hist = [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd, macd_sinyal)
    ]
    stoch_k, stoch_d = _stochastic_serisi(highs, lows, closes, 14, 3)
    adx = _adx_serisi(highs, lows, closes, 14)
    obv = _obv_serisi(closes, volumes)

    # Görüntülenecek aralığa geri kırp -- ısınma payı yalnızca hesap içindi.
    baslangic = next((i for i, d in enumerate(dates) if d >= cutoff), 0)

    def dilimle(seri):
        return seri[baslangic:]

    result = {
        "available": True,
        "dates": [d.isoformat() for d in dilimle(dates)],
        "sma20": dilimle(sma20),
        "sma50": dilimle(sma50),
        "sma200": dilimle(sma200),
        "ema20": dilimle(ema20),
        "bollinger_upper": dilimle(bb_ust),
        "bollinger_mid": dilimle(bb_orta),
        "bollinger_lower": dilimle(bb_alt),
        "rsi14": dilimle(rsi14),
        "macd": dilimle(macd),
        "macd_signal": dilimle(macd_sinyal),
        "macd_hist": dilimle(macd_hist),
        "stochastic_k": dilimle(stoch_k),
        "stochastic_d": dilimle(stoch_d),
        "adx": dilimle(adx),
        "obv": dilimle(obv),
    }

    with _cache_lock:
        _cache[cache_key] = (now, result)
    return result
