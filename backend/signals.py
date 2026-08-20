"""
signals.py
----------
Teknik sinyal taraması — ücretli terminallerin "formasyon/tarama analizi"
başlığı altında sunduğu özelliğin karşılığı.

Tüm hesaplar kendi stock_prices_daily tablomuzdaki günlük OHLCV barlarından
yapılır; ek veri kaynağı gerekmez.

Tasarım notu — SİNYAL "BUGÜN OLUŞMUŞ" OLMALIDIR:
Altın kesişim gibi olaylar bir kez gerçekleşir; "SMA50 > SMA200" koşulu ise
kesişimden sonra aylarca doğru kalır. Koşulu doğrudan raporlamak, aylar önce
olmuş bir kesişimi her gün "yeni sinyal" gibi göstermek olurdu. Bu yüzden
kesişim sinyalleri, koşulun BUGÜN doğru ve BİR ÖNCEKİ GÜN yanlış olmasına
göre üretilir.
"""

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

import models

# --- Tarama sonucu önbelleği -------------------------------------------------
# Tarama TÜM hisselerin tüm günlük barlarını (50k+ satır) okuyup Python'da
# hesaplıyor; ölçümde ~2.6 sn sürüyordu ve her sayfa açılışında tekrarlanması
# hem yavaş hem gereksizdi. Sinyaller GÜNLÜK barlardan üretildiği için gün
# içinde değişmez; 30 dakikalık önbellek fazlasıyla taze kalır.
_CACHE_TTL_SECONDS = 1800
_cache_lock = threading.Lock()
_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}


def _sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _rsi(values: List[float], period: int = 14) -> Optional[float]:
    """Wilder RSI. Yeterli bar yoksa None."""
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for i in range(len(values) - period, len(values)):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _detect_for_stock(symbol: str, company: str, bars: List[Any]) -> List[Dict[str, Any]]:
    """Tek bir hisse için sinyalleri üretir. `bars` tarihe göre ARTAN sıralı olmalı."""
    closes = [float(b.close) for b in bars]
    volumes = [float(b.volume) for b in bars if b.volume is not None]
    if len(closes) < 60:
        return []

    out: List[Dict[str, Any]] = []
    last_price = closes[-1]

    def add(kind: str, direction: str, title: str, detail: str):
        out.append({
            "symbol": symbol, "company_name": company, "signal_type": kind,
            "direction": direction, "title": title, "detail": detail,
            "price": round(last_price, 2),
        })

    # --- Hareketli ortalama kesişimleri (yalnızca BUGÜN oluşmuşsa) ---
    sma50_now, sma200_now = _sma(closes, 50), _sma(closes, 200)
    sma50_prev, sma200_prev = _sma(closes[:-1], 50), _sma(closes[:-1], 200)
    if None not in (sma50_now, sma200_now, sma50_prev, sma200_prev):
        if sma50_prev <= sma200_prev and sma50_now > sma200_now:
            add("GOLDEN_CROSS", "AL", "Altın Kesişim",
                "50 günlük ortalama 200 günlüğü yukarı kesti — uzun vadeli yükseliş sinyali sayılır.")
        elif sma50_prev >= sma200_prev and sma50_now < sma200_now:
            add("DEATH_CROSS", "SAT", "Ölüm Kesişimi",
                "50 günlük ortalama 200 günlüğü aşağı kesti — uzun vadeli zayıflık sinyali sayılır.")

    # --- RSI aşırı bölgeler ---
    rsi = _rsi(closes)
    if rsi is not None:
        if rsi < 30:
            add("RSI_OVERSOLD", "AL", f"Aşırı Satım (RSI {rsi:.0f})",
                "RSI 30'un altında — hisse aşırı satılmış kabul edilir, tepki yükselişi görülebilir.")
        elif rsi > 70:
            add("RSI_OVERBOUGHT", "SAT", f"Aşırı Alım (RSI {rsi:.0f})",
                "RSI 70'in üzerinde — hisse aşırı alınmış kabul edilir, kâr satışı görülebilir.")

    # --- Hacim patlaması ---
    # Son barın hacmi, önceki 20 barın ortalamasının 2 katını aşıyorsa.
    if len(volumes) >= 21:
        avg20 = sum(volumes[-21:-1]) / 20
        if avg20 > 0 and volumes[-1] > avg20 * 2:
            add("VOLUME_SPIKE", "DIKKAT", f"Hacim Patlaması ({volumes[-1] / avg20:.1f}x)",
                "Günlük işlem hacmi 20 günlük ortalamanın 2 katını aştı — güçlü ilgi veya haber akışı olabilir.")

    # --- 52 hafta zirve/dip kırılımı ---
    # 252 iş günü ~ 52 hafta. Kırılımın BUGÜN olması için önceki barın zirveyi
    # aşmamış olması aranır; aksi halde zirvede kalan hisse her gün listelenirdi.
    window = closes[-252:] if len(closes) >= 252 else closes
    if len(window) >= 100:
        high52, low52 = max(window[:-1]), min(window[:-1])
        if last_price > high52:
            add("NEW_52W_HIGH", "AL", "52 Hafta Zirvesi",
                f"Fiyat son 52 haftanın en yükseğini ({high52:.2f} TL) aştı.")
        elif last_price < low52:
            add("NEW_52W_LOW", "SAT", "52 Hafta Dibi",
                f"Fiyat son 52 haftanın en düşüğünün ({low52:.2f} TL) altına indi.")

    return out


def scan_signals(db: Session, limit_per_stock: int = 300, use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Tüm aktif hisseleri tarar ve bugün oluşan teknik sinyalleri döner.

    Tek sorguda tüm barlar çekilip Python'da gruplanır; hisse başına ayrı
    sorgu atmak 43 sorgu demek olurdu.
    """
    if use_cache:
        with _cache_lock:
            entry = _cache.get("all")
            if entry and (time.time() - entry[0]) < _CACHE_TTL_SECONDS:
                return entry[1]

    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    if not stocks:
        return []

    by_id = {s.id: s for s in stocks}
    rows = (
        db.query(models.StockPriceDaily)
        .filter(models.StockPriceDaily.stock_id.in_(list(by_id.keys())))
        .order_by(models.StockPriceDaily.stock_id.asc(), models.StockPriceDaily.trade_date.asc())
        .all()
    )

    grouped: Dict[int, List[Any]] = {}
    for r in rows:
        grouped.setdefault(r.stock_id, []).append(r)

    results: List[Dict[str, Any]] = []
    for stock_id, bars in grouped.items():
        stock = by_id.get(stock_id)
        if not stock:
            continue
        results.extend(_detect_for_stock(stock.symbol, stock.company_name, bars[-limit_per_stock:]))

    # AL sinyalleri üstte, sonra DİKKAT, sonra SAT; kendi içinde sembole göre.
    order = {"AL": 0, "DIKKAT": 1, "SAT": 2}
    results.sort(key=lambda x: (order.get(x["direction"], 3), x["symbol"]))

    if use_cache:
        with _cache_lock:
            _cache["all"] = (time.time(), results)
    return results
