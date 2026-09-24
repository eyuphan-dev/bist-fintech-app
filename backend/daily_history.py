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
# Endeks geçmişi (BIST 100 + BIST 30 + Banka + Katılım) — kıyaslama ve şerit için
# ---------------------------------------------------------------------------
BENCHMARK_SYMBOL = "XU100"
BENCHMARK_YAHOO = "XU100.IS"

# Uygulamanın izlediği endeksler: iç sembol -> Yahoo sembolü. XU100 portföy
# kıyaslamasının referansıdır (bkz. main.py get_portfolio_benchmark); diğerleri
# yalnızca piyasa şeridinde gösterilir.
#
# NOT: Yahoo, katılım endekslerinde (XKTUM, XK030) GEÇMİŞ vermiyor, yalnızca son
# değeri veriyor (3 aylık istekte tek bar döner). Bu yüzden onların günlük
# değişimi kendi biriktirdiğimiz satırlardan hesaplanır ve ilk gün boş kalır --
# değişim uydurulmaz.
ENDEKSLER = {
    "XU100": "XU100.IS",
    "XU030": "XU030.IS",
    "XBANK": "XBANK.IS",
    "XKTUM": "XKTUM.IS",
    "XK030": "XK030.IS",
}


def _endeks_gecmisi_yaz(db, symbol: str, yahoo: str, period: str) -> int:
    import yfinance as yf
    import models
    from yf_retry import call_with_retry

    try:
        hist = call_with_retry(
            lambda: yf.Ticker(yahoo).history(period=period, interval="1d"),
            attempts=2, label=f"{symbol}.history",
        )
    except Exception as e:
        print(f"[IndexHistory] {symbol} verisi çekilemedi: {e}")
        return 0

    if hist is None or hist.empty:
        print(f"[IndexHistory] {symbol} için veri dönmedi.")
        return 0

    existing = {
        row.trade_date: row
        for row in db.query(models.IndexHistory).filter_by(symbol=symbol).all()
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
            db.add(models.IndexHistory(symbol=symbol, trade_date=d, close=close))
        written += 1

    db.commit()
    print(f"[IndexHistory] {symbol}: {written} günlük kapanış işlendi.")
    return written


def refresh_index_history(db, period: str = "1y") -> int:
    """
    İzlenen endekslerin günlük kapanışlarını çeker ve index_history'e yazar.

    XU100, kullanıcının portföy getirisini endekse karşı kıyaslamak için gerekir
    ("endeksi yenebiliyor muyum?"). Endeksler bir hisse olmadığı için stocks
    tablosuna değil kendi tablosuna yazılır. Bir endeksin çekilememesi diğerlerini
    ETKİLEMEZ.

    Idempotent: aynı (symbol, trade_date) için tekrar çalıştırılırsa kapanış
    güncellenir, yeni satır açılmaz (UNIQUE kısıtı bunu garanti eder).
    """
    toplam = 0
    for symbol, yahoo in ENDEKSLER.items():
        toplam += _endeks_gecmisi_yaz(db, symbol, yahoo, period)
    return toplam


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

    ARTIK KULLANILMIYOR — bkz. tr_market.py.

    Bu fonksiyon USDTRY/EURTRY/GRAMALTIN'i günde bir kez (TR 11:00) yazıyordu
    ve gram altını ons altından TÜRETİYORDU. Ons için `GC=F`, yani COMEX VADELİ
    sözleşmesi kullanılıyordu; vadeli spotun üzerinde işlem görür. Ölçüldü:
    GC=F 4695,60 USD iken spot ons 4641,83 USD (contango %1,16), bunun gram
    altına yansıması 7251,81 TL yerine olması gereken 7175,52 TL idi.

    Yerine yurt içi kaynaktan 15 dakikada bir anlık kur yazan
    tr_market.store_tr_quotes() geçti. Fonksiyon SİLİNMEDİ çünkü tr_market'in
    dayandığı dış kaynak kalıcı olarak düşerse geri dönülebilecek tek şey bu —
    ama geri dönülürse yukarıdaki sapmanın bilinerek kabul edilmesi gerekir.
    Zamanlayıcıya BAĞLI DEĞİLDİR; elle çağrılmadıkça çalışmaz.
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
