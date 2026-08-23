"""
financials.py
-------------
Çeyreklik finansal tablo (gelir tablosu / bilanço / nakit akışı) çekimi.

Ücretli platformların (Fintables vb.) paket içinde sunduğu "finansal tablolar"
özelliğinin karşılığıdır; veri yfinance'ta ücretsiz olduğu için burada da
sunulur. BIST şirketlerinde genellikle son 6 çeyrek gelir.

Tasarım notu — SATIR ADLARI SABİT DEĞİLDİR:
yfinance'in döndürdüğü tabloda satır etiketleri şirketten şirkete ve sürümden
sürüme değişebiliyor ("Total Revenue" / "Operating Revenue", "Net Income" /
"Net Income Common Stockholders" gibi). Bu yüzden alanlar tam eşleşme yerine
öncelik sıralı aday listesiyle aranır; ilk bulunan kullanılır.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

import models
from yf_retry import call_with_retry

# Alan -> aday satır etiketleri (öncelik sırasıyla).
INCOME_FIELDS = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "Total Operating Income As Reported"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "net_income": ["Net Income Common Stockholders", "Net Income", "Net Income From Continuing Operations"],
}
BALANCE_FIELDS = {
    "total_assets": ["Total Assets"],
    "total_equity": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
    "total_debt": ["Total Debt", "Net Debt"],
    # Katılım taraması için: nakit ve kısa vadeli finansal yatırımlar.
    "cash_and_equivalents": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash Financial"],
    "short_term_investments": ["Other Short Term Investments", "Short Term Investments", "Available For Sale Securities"],
}
CASHFLOW_FIELDS = {
    "operating_cashflow": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "free_cashflow": ["Free Cash Flow"],
}


def _pick(frame, candidates: List[str], column) -> Optional[float]:
    """Aday etiketlerden ilk bulunanın değerini döner; hiçbiri yoksa None."""
    if frame is None or getattr(frame, "empty", True):
        return None
    index_map = {str(i): i for i in frame.index}
    for name in candidates:
        key = index_map.get(name)
        if key is None:
            continue
        try:
            value = frame.loc[key, column]
        except Exception:
            continue
        if value is None:
            continue
        try:
            f = float(value)
        except (TypeError, ValueError):
            continue
        # yfinance boş hücreleri NaN olarak döndürür; NaN kendine eşit değildir.
        if f != f:
            continue
        return f
    return None


def refresh_financials_for_stock(db: Session, symbol: str, max_periods: int = 6) -> int:
    """
    Tek bir hissenin çeyreklik finansal tablolarını çeker ve kaydeder.

    Idempotent: aynı (stock_id, period_end) için tekrar çalıştırılırsa satır
    güncellenir, yenisi eklenmez (UNIQUE kısıtı bunu garanti eder).
    """
    import yfinance as yf

    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return 0

    ticker = yf.Ticker(f"{symbol.upper()}.IS")
    try:
        income = call_with_retry(lambda: ticker.quarterly_financials, attempts=2, label=f"{symbol}.q_financials")
        balance = call_with_retry(lambda: ticker.quarterly_balance_sheet, attempts=2, label=f"{symbol}.q_balance")
        cash = call_with_retry(lambda: ticker.quarterly_cashflow, attempts=2, label=f"{symbol}.q_cashflow")
    except Exception as e:
        print(f"[Financials] {symbol}: veri çekilemedi ({e})")
        return 0

    if income is None or getattr(income, "empty", True):
        return 0

    existing = {
        row.period_end: row
        for row in db.query(models.FinancialStatement).filter_by(stock_id=stock.id).all()
    }

    written = 0
    for column in list(income.columns)[:max_periods]:
        try:
            period_end = column.date()
        except Exception:
            continue

        values: Dict[str, Any] = {}
        for field, candidates in INCOME_FIELDS.items():
            values[field] = _pick(income, candidates, column)
        for field, candidates in BALANCE_FIELDS.items():
            values[field] = _pick(balance, candidates, column) if balance is not None else None
        for field, candidates in CASHFLOW_FIELDS.items():
            values[field] = _pick(cash, candidates, column) if cash is not None else None

        # Hiçbir alan dolmadıysa boş satır yazmanın anlamı yok.
        if all(v is None for v in values.values()):
            continue

        row = existing.get(period_end)
        if row:
            for field, value in values.items():
                setattr(row, field, value)
        else:
            db.add(models.FinancialStatement(stock_id=stock.id, period_end=period_end, **values))
        written += 1

    db.commit()
    return written


def refresh_financials_batch(db: Session, batch_size: int = 8) -> int:
    """
    En bayat `batch_size` hissenin finansal tablolarını tazeler.

    Hisse başına 3 ayrı yfinance çağrısı (gelir/bilanço/nakit) gerektiği için
    tüm katalog tek seferde işlenmez; parti parti dönülür.
    """
    import time

    rows = (
        db.query(models.Stock)
        .outerjoin(models.FinancialStatement, models.FinancialStatement.stock_id == models.Stock.id)
        .filter(models.Stock.is_active == True)
        .order_by(models.FinancialStatement.updated_at.asc().nullsfirst())
        .limit(batch_size)
        .all()
    )

    total = 0
    print(f"[Financials] Finansal tablolar tazeleniyor ({len(rows)} hisse)...")
    for i, stock in enumerate(rows):
        if i > 0:
            time.sleep(1.0)
        try:
            n = refresh_financials_for_stock(db, stock.symbol)
            if n:
                total += 1
                print(f"[Financials]   {stock.symbol}: {n} dönem")
            # Temettü geçmişi aynı turda çekilir — ek bir zamanlanmış iş
            # gerektirmeyecek kadar hafif (tek yfinance çağrısı).
            refresh_dividend_history(db, stock.symbol)
        except Exception as e:
            print(f"[Financials]   {stock.symbol}: hata ({e})")
            db.rollback()

    print(f"[Financials] Tamamlandı: {total}/{len(rows)} hisse.")
    return total


# ---------------------------------------------------------------------------
# Temettü ödeme geçmişi
# ---------------------------------------------------------------------------
def refresh_dividend_history(db: Session, symbol: str) -> int:
    """
    Hissenin geçmiş temettü ödemelerini çeker.

    Idempotent: aynı (stock_id, pay_date) tekrar gelirse tutar güncellenir.
    yfinance temettüleri fiyat düzeltmesi uygulanmış olarak döndürebilir; bu
    yüzden geçmiş kayıtlar da her tazelemede güncellenir, salt eklenmez.
    """
    import yfinance as yf

    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return 0

    try:
        series = call_with_retry(
            lambda: yf.Ticker(f"{symbol.upper()}.IS").dividends,
            attempts=2, label=f"{symbol}.dividends",
        )
    except Exception as e:
        print(f"[Dividends] {symbol}: çekilemedi ({e})")
        return 0

    if series is None or len(series) == 0:
        return 0

    existing = {
        r.pay_date: r
        for r in db.query(models.DividendHistory).filter_by(stock_id=stock.id).all()
    }

    written = 0
    for idx, value in series.items():
        try:
            d = idx.date()
            amount = float(value)
        except Exception:
            continue
        if amount <= 0:
            continue

        row = existing.get(d)
        if row:
            row.amount = amount
        else:
            db.add(models.DividendHistory(stock_id=stock.id, pay_date=d, amount=amount))
        written += 1

    db.commit()
    return written
