"""
daily_history.py
-----------------
Hisse detay grafiğindeki uzun vadeli aralıklar (1H/1A/1Y/5Y) için günlük
kapanış barlarını (OHLCV) yfinance'tan çekip stock_prices_daily tablosuna
yazan servis. stock_prices (5 dakikalık gün-içi tikler) tablosundan bilerek
ayrı tutulur (bkz. models.py:StockPriceDaily docstring).

Strateji:
  - Bir hissenin hiç günlük kaydı yoksa: TAM 5 yıllık geçmiş tek seferde çekilir
    (ilk kurulum / yeni eklenen hisse).
  - Zaten kaydı varsa: sadece son birkaç günü (varsayılan 5 gün) tekrar çekip
    upsert edilir — böylece hem her gün taze kapanış eklenir hem de olası
    revizyonlar (örn. hacim düzeltmesi) yakalanır. Her gün TÜM 5 yılı yeniden
    çekmek gereksiz yere proxy/Yahoo kotasını tüketir.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import models
from yfinance_client import fetch_daily_history


def refresh_daily_history(db: Session, stock_codes: Optional[list] = None) -> int:
    """
    Aktif hisseler için günlük OHLCV geçmişini günceller.
    stock_codes verilirse sadece o semboller işlenir (örn. yeni eklenen hisse).
    Döner: güncellenen/eklenen hisse sayısı.
    """
    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    if stock_codes:
        wanted = {c.upper() for c in stock_codes}
        stocks = [s for s in stocks if s.symbol.upper() in wanted]

    updated = 0
    for stock in stocks:
        has_existing = (
            db.query(models.StockPriceDaily)
            .filter_by(stock_id=stock.id)
            .first()
            is not None
        )
        period = "5d" if has_existing else "5y"

        bars = fetch_daily_history(stock.symbol, period=period)
        if not bars:
            continue

        for bar in bars:
            existing = (
                db.query(models.StockPriceDaily)
                .filter_by(stock_id=stock.id, trade_date=bar["trade_date"])
                .first()
            )
            if existing:
                existing.open = bar["open"]
                existing.high = bar["high"]
                existing.low = bar["low"]
                existing.close = bar["close"]
                existing.volume = bar["volume"]
            else:
                db.add(models.StockPriceDaily(
                    stock_id=stock.id,
                    trade_date=bar["trade_date"],
                    open=bar["open"],
                    high=bar["high"],
                    low=bar["low"],
                    close=bar["close"],
                    volume=bar["volume"],
                ))
        db.commit()
        updated += 1

    print(f"[DailyHistory] {updated} hisse için günlük geçmiş güncellendi.")
    return updated


# ---------------------------------------------------------------------------
# BIST 100 (XU100) endeks geçmişi — portföy/endeks kıyaslaması için
# ---------------------------------------------------------------------------
BENCHMARK_SYMBOL = "XU100"
BENCHMARK_YAHOO = "XU100.IS"


def refresh_index_history(db, period: str = "1y") -> int:
    """
    BIST 100 endeksinin günlük kapanışlarını çeker ve index_history'e yazar.

    Kullanıcının portföy getirisini endekse karşı kıyaslamak için gerekir
    ("endeksi yenebiliyor muyum?"). Endeks bir hisse olmadığı için stocks
    tablosuna değil kendi tablosuna yazılır.

    Idempotent: aynı (symbol, trade_date) için tekrar çalıştırılırsa kapanış
    güncellenir, yeni satır açılmaz (UNIQUE kısıtı bunu garanti eder).
    """
    import yfinance as yf
    import models
    from yf_retry import call_with_retry

    try:
        hist = call_with_retry(
            lambda: yf.Ticker(BENCHMARK_YAHOO).history(period=period, interval="1d"),
            attempts=2, label="XU100.history",
        )
    except Exception as e:
        print(f"[IndexHistory] XU100 verisi çekilemedi: {e}")
        return 0

    if hist is None or hist.empty:
        print("[IndexHistory] XU100 için veri dönmedi.")
        return 0

    existing = {
        row.trade_date: row
        for row in db.query(models.IndexHistory).filter_by(symbol=BENCHMARK_SYMBOL).all()
    }

    written = 0
    for idx, row in hist.iterrows():
        try:
            d = idx.date()
            close = float(row["Close"])
        except Exception:
            continue
        if close <= 0:
            continue

        current = existing.get(d)
        if current:
            current.close = close
        else:
            db.add(models.IndexHistory(symbol=BENCHMARK_SYMBOL, trade_date=d, close=close))
        written += 1

    db.commit()
    print(f"[IndexHistory] XU100: {written} günlük kapanış işlendi.")
    return written


# ---------------------------------------------------------------------------
# Döviz & Altın — Türk yatırımcının hisse yanında sürekli izlediği referanslar
# ---------------------------------------------------------------------------
# Yahoo sembolleri. Gram altın doğrudan bir sembol olarak yok; ons altın (USD)
# ve USD/TRY birleştirilerek türetilir (bkz. refresh_market_quotes).
MARKET_QUOTES = {
    "USDTRY": "USDTRY=X",
    "EURTRY": "EURTRY=X",
    "XAUUSD": "GC=F",      # ons altın, USD
}
GRAM_PER_OUNCE = 31.1034768


def refresh_market_quotes(db, period: str = "3mo") -> int:
    """
    Döviz kurları ve altın fiyatlarının günlük kapanışlarını index_history'e yazar.

    Endeksle aynı tabloyu kullanır çünkü veri şekli birebir aynıdır
    (sembol + gün + kapanış) ve bunlar da hisse değil "referans seri"dir.

    GRAMALTIN türetilmiş bir seridir: ons altın (USD) × USD/TRY ÷ 31.1034768.
    Yalnızca her iki serinin de kapanışının bulunduğu günler için hesaplanır —
    aksi halde eksik günde yanlış bir kur eşleşmesiyle saçma bir gram fiyatı
    üretilirdi.
    """
    import yfinance as yf
    import models
    from yf_retry import call_with_retry

    closes_by_symbol: dict[str, dict] = {}

    for key, yahoo_symbol in MARKET_QUOTES.items():
        try:
            hist = call_with_retry(
                lambda: yf.Ticker(yahoo_symbol).history(period=period, interval="1d"),
                attempts=2, label=f"{key}.history",
            )
        except Exception as e:
            print(f"[MarketQuotes] {key} çekilemedi: {e}")
            continue
        if hist is None or hist.empty:
            continue
        closes_by_symbol[key] = {
            idx.date(): float(row["Close"])
            for idx, row in hist.iterrows()
            if float(row["Close"]) > 0
        }

    # Gram altın: yalnızca iki serinin de bulunduğu günlerde türetilir.
    usd = closes_by_symbol.get("USDTRY", {})
    xau = closes_by_symbol.get("XAUUSD", {})
    common_days = set(usd) & set(xau)
    if common_days:
        closes_by_symbol["GRAMALTIN"] = {
            d: (xau[d] * usd[d]) / GRAM_PER_OUNCE for d in common_days
        }

    written = 0
    for symbol, series in closes_by_symbol.items():
        existing = {
            r.trade_date: r
            for r in db.query(models.IndexHistory).filter_by(symbol=symbol).all()
        }
        for d, close in series.items():
            row = existing.get(d)
            if row:
                row.close = round(close, 2)
            else:
                db.add(models.IndexHistory(symbol=symbol, trade_date=d, close=round(close, 2)))
            written += 1

    db.commit()
    print(f"[MarketQuotes] {len(closes_by_symbol)} seri, {written} kapanış işlendi.")
    return written
