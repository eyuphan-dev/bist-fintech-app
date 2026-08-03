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
