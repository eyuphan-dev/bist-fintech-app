"""
analysis_engine.py
-------------------
Derin Bilanço Analizi Motoru: Piotroski Skoru, Graham Makul Değeri,
Temettü Hedefi Hesaplayıcı ve Düzenli Yatırım (DCA) Geriye Dönük Testi.

Veri kaynağı: yfinance (ticker.info / financials / balance_sheet).
BİST'te bazı hisseler için finansal alanlar eksik olabilir; eksik veri
durumunda ilgili alan None bırakılır, hesaplama patlamaz. Ancak yfinance'a
hiç ulaşılamazsa (ağ hatası vb.) bu durum AnalysisFetchError olarak
yükseltilir ki çağıran taraf (main.py) sessizce "başarılı" dönmesin.
"""

import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import yfinance as yf
from sqlalchemy import text
from sqlalchemy.orm import Session

import models


class AnalysisFetchError(Exception):
    """yfinance'tan veri çekilemediğinde (ağ hatası, sembol geçersiz vb.) yükseltilir."""
    pass


# ---------------------------------------------------------------------------
# Yardımcı: güvenli sayısal erişim
# ---------------------------------------------------------------------------
def _safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b in (None, 0):
        return None
    return a / b


# ---------------------------------------------------------------------------
# Piotroski F-Skoru (0-9): karlılık, kaldıraç/likidite, verimlilik kriterleri
# ---------------------------------------------------------------------------
def _calculate_piotroski_score(ticker: yf.Ticker) -> Optional[int]:
    try:
        financials = ticker.financials
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow

        if financials.empty or balance_sheet.empty or len(financials.columns) < 2:
            return None

        cur, prev = financials.columns[0], financials.columns[1]
        bs_cur, bs_prev = balance_sheet.columns[0], balance_sheet.columns[1]

        net_income_cur = _safe_float(financials.loc["Net Income", cur]) if "Net Income" in financials.index else None
        net_income_prev = _safe_float(financials.loc["Net Income", prev]) if "Net Income" in financials.index else None
        total_assets_cur = _safe_float(balance_sheet.loc["Total Assets", bs_cur]) if "Total Assets" in balance_sheet.index else None
        total_assets_prev = _safe_float(balance_sheet.loc["Total Assets", bs_prev]) if "Total Assets" in balance_sheet.index else None

        op_cashflow = None
        if not cashflow.empty and "Operating Cash Flow" in cashflow.index:
            op_cashflow = _safe_float(cashflow.loc["Operating Cash Flow", cashflow.columns[0]])

        long_term_debt_cur = _safe_float(balance_sheet.loc["Long Term Debt", bs_cur]) if "Long Term Debt" in balance_sheet.index else None
        long_term_debt_prev = _safe_float(balance_sheet.loc["Long Term Debt", bs_prev]) if "Long Term Debt" in balance_sheet.index else None

        current_assets_cur = _safe_float(balance_sheet.loc["Current Assets", bs_cur]) if "Current Assets" in balance_sheet.index else None
        current_liab_cur = _safe_float(balance_sheet.loc["Current Liabilities", bs_cur]) if "Current Liabilities" in balance_sheet.index else None
        current_assets_prev = _safe_float(balance_sheet.loc["Current Assets", bs_prev]) if "Current Assets" in balance_sheet.index else None
        current_liab_prev = _safe_float(balance_sheet.loc["Current Liabilities", bs_prev]) if "Current Liabilities" in balance_sheet.index else None

        gross_profit_cur = _safe_float(financials.loc["Gross Profit", cur]) if "Gross Profit" in financials.index else None
        gross_profit_prev = _safe_float(financials.loc["Gross Profit", prev]) if "Gross Profit" in financials.index else None
        revenue_cur = _safe_float(financials.loc["Total Revenue", cur]) if "Total Revenue" in financials.index else None
        revenue_prev = _safe_float(financials.loc["Total Revenue", prev]) if "Total Revenue" in financials.index else None

        score = 0

        # 1. Pozitif net kâr
        if net_income_cur is not None and net_income_cur > 0:
            score += 1
        # 2. Pozitif işletme nakit akışı
        if op_cashflow is not None and op_cashflow > 0:
            score += 1
        # 3. Aktif kârlılığı (ROA) artışı
        roa_cur = _safe_div(net_income_cur, total_assets_cur)
        roa_prev = _safe_div(net_income_prev, total_assets_prev)
        if roa_cur is not None and roa_prev is not None and roa_cur > roa_prev:
            score += 1
        # 4. Nakit akışı net kârdan büyük (kâr kalitesi)
        if op_cashflow is not None and net_income_cur is not None and op_cashflow > net_income_cur:
            score += 1
        # 5. Uzun vadeli borç azalışı (kaldıraç düşüşü)
        if long_term_debt_cur is not None and long_term_debt_prev is not None and long_term_debt_cur < long_term_debt_prev:
            score += 1
        # 6. Cari oran artışı (likidite iyileşmesi)
        current_ratio_cur = _safe_div(current_assets_cur, current_liab_cur)
        current_ratio_prev = _safe_div(current_assets_prev, current_liab_prev)
        if current_ratio_cur is not None and current_ratio_prev is not None and current_ratio_cur > current_ratio_prev:
            score += 1
        # 7. Hisse sayısında seyreltme olmaması (varsayılan: veri yoksa puan verilmez)
        shares_cur = _safe_float(balance_sheet.loc["Ordinary Shares Number", bs_cur]) if "Ordinary Shares Number" in balance_sheet.index else None
        shares_prev = _safe_float(balance_sheet.loc["Ordinary Shares Number", bs_prev]) if "Ordinary Shares Number" in balance_sheet.index else None
        if shares_cur is not None and shares_prev is not None and shares_cur <= shares_prev:
            score += 1
        # 8. Brüt kâr marjı artışı
        gm_cur = _safe_div(gross_profit_cur, revenue_cur)
        gm_prev = _safe_div(gross_profit_prev, revenue_prev)
        if gm_cur is not None and gm_prev is not None and gm_cur > gm_prev:
            score += 1
        # 9. Aktif devir hızı artışı (verimlilik)
        turnover_cur = _safe_div(revenue_cur, total_assets_cur)
        turnover_prev = _safe_div(revenue_prev, total_assets_prev)
        if turnover_cur is not None and turnover_prev is not None and turnover_cur > turnover_prev:
            score += 1

        return score
    except Exception as e:
        print(f"[AnalysisEngine] Piotroski hesaplama hatası: {e}")
        return None


def _graham_fair_value(eps: Optional[float], book_value_per_share: Optional[float]) -> Optional[float]:
    """Graham Formülü: √(22.5 × EPS × BVPS). Negatif/eksik girdilerde None döner."""
    if eps is None or book_value_per_share is None or eps <= 0 or book_value_per_share <= 0:
        return None
    return round(math.sqrt(22.5 * eps * book_value_per_share), 2)


def _fx_exposure_text(info: Dict[str, Any]) -> str:
    """Döviz kuru riskine dair kaba (heuristic) bir değerlendirme metni üretir."""
    sector = (info.get("sector") or "").lower()
    industry = (info.get("industry") or "").lower()
    export_heavy = any(k in industry or k in sector for k in ["textile", "auto", "steel", "chemical", "airlines", "tekstil", "otomotiv"])
    if export_heavy:
        return "Sektör ağırlıklı ihracat/ithalat yapısı nedeniyle döviz kuru dalgalanmalarına orta-yüksek düzeyde duyarlıdır."
    return "Şirketin döviz kuru riskine duyarlılığı, mevcut halka açık verilerle sınırlı düzeyde değerlendirilmiştir; detay için faaliyet raporuna bakınız."


def _interest_sensitivity_text(info: Dict[str, Any]) -> str:
    total_debt = _safe_float(info.get("totalDebt"))
    total_cash = _safe_float(info.get("totalCash"))
    if total_debt is not None and total_cash is not None:
        net_debt = total_debt - total_cash
        if net_debt > 0:
            return "Net borçlu pozisyonda; faiz oranlarındaki artışlar finansman giderlerini yükseltebilir."
        return "Net nakit pozisyonunda; faiz artışlarından finansman gideri açısından görece az etkilenir."
    return "Faiz hassasiyeti, yeterli bilanço verisi bulunmadığından değerlendirilememiştir."


# ---------------------------------------------------------------------------
# TASK: calculate_deep_analysis(symbol)
# ---------------------------------------------------------------------------
def calculate_deep_analysis(db: Session, symbol: str, sector_pe_avg_override: Optional[float] = None) -> Optional[models.CompanyAnalysis]:
    """
    Piotroski skoru, F/K, PD/DD, FD/FAVÖK, Graham makul değer, ROE, kâr marjları,
    döviz/faiz hassasiyeti metinlerini hesaplayıp company_analysis tablosuna yazar.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        print(f"[AnalysisEngine] Hisse bulunamadı: {symbol}")
        return None

    yahoo_symbol = f"{symbol.upper()}.IS"
    try:
        ticker = yf.Ticker(yahoo_symbol)
        info = ticker.info or {}
    except Exception as e:
        print(f"[AnalysisEngine] yfinance bilgi çekme hatası ({symbol}): {e}")
        raise AnalysisFetchError(
            f"{symbol.upper()} için yfinance'tan veri alınamadı. Ağ bağlantısını veya sembolü kontrol edin. Detay: {e}"
        ) from e

    if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None and info.get("previousClose") is None):
        raise AnalysisFetchError(
            f"{symbol.upper()} için yfinance geçerli bir veri döndürmedi (boş yanıt). Sembol BİST'te işlem görmüyor olabilir ya da veri sağlayıcı geçici olarak erişilemez durumda."
        )

    pe_ratio = _safe_float(info.get("trailingPE"))
    pb_ratio = _safe_float(info.get("priceToBook"))
    ev_ebitda = _safe_float(info.get("enterpriseToEbitda"))
    roe = _safe_float(info.get("returnOnEquity"))
    gross_margin = _safe_float(info.get("grossMargins"))
    net_margin = _safe_float(info.get("profitMargins"))
    eps = _safe_float(info.get("trailingEps"))
    book_value = _safe_float(info.get("bookValue"))

    fair_value = _graham_fair_value(eps, book_value)
    current_price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    discount_rate = None
    if fair_value and current_price and current_price > 0:
        discount_rate = round(((fair_value - current_price) / current_price) * 100, 2)

    piotroski = None
    try:
        piotroski = _calculate_piotroski_score(ticker)
    except Exception as e:
        print(f"[AnalysisEngine] Piotroski hesaplama başarısız ({symbol}): {e}")

    analysis = db.query(models.CompanyAnalysis).filter_by(stock_id=stock.id).first()
    if not analysis:
        analysis = models.CompanyAnalysis(stock_id=stock.id)
        db.add(analysis)

    analysis.piotroski_score = piotroski
    analysis.pe_ratio = pe_ratio
    analysis.pb_ratio = pb_ratio
    analysis.ev_ebitda = ev_ebitda
    analysis.sector_pe_avg = sector_pe_avg_override
    analysis.fair_value = fair_value
    analysis.discount_rate = discount_rate
    analysis.roe = round(roe * 100, 2) if roe is not None else None
    analysis.gross_margin = round(gross_margin * 100, 2) if gross_margin is not None else None
    analysis.net_margin = round(net_margin * 100, 2) if net_margin is not None else None
    analysis.fx_exposure_text = _fx_exposure_text(info)
    analysis.interest_sensitivity_text = _interest_sensitivity_text(info)
    analysis.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(analysis)
    print(f"[AnalysisEngine] {symbol}: Piotroski={piotroski}, F/K={pe_ratio}, Makul Değer={fair_value}")
    return analysis


def calculate_sector_pe_averages(db: Session) -> Dict[int, float]:
    """Aktif hisseler için F/K oranlarını çekip basit ortalama (piyasa geneli) döner."""
    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    pe_values: List[float] = []
    for stock in stocks:
        try:
            info = yf.Ticker(f"{stock.symbol}.IS").info or {}
            pe = _safe_float(info.get("trailingPE"))
            if pe and pe > 0:
                pe_values.append(pe)
        except Exception:
            continue
    avg = round(sum(pe_values) / len(pe_values), 2) if pe_values else None
    return {stock.id: avg for stock in stocks}


# ---------------------------------------------------------------------------
# TASK: calculate_dividend_goal(symbol, target_monthly_income)
# ---------------------------------------------------------------------------
def calculate_dividend_goal(db: Session, symbol: str, target_monthly_income: float) -> Optional[Dict[str, Any]]:
    """
    Hedeflenen aylık pasif gelire ulaşmak için gereken lot sayısı ve
    gerekli sermayeyi hesaplar. yfinance 'dividendYield' ve 'currentPrice' kullanır.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return None

    try:
        info = yf.Ticker(f"{symbol.upper()}.IS").info or {}
    except Exception as e:
        print(f"[AnalysisEngine] Temettü verisi çekme hatası ({symbol}): {e}")
        info = {}

    dividend_yield = _safe_float(info.get("dividendYield"))  # oransal, örn. 0.05
    current_price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))

    latest_record = (
        db.query(models.StockPrice)
        .filter_by(stock_id=stock.id)
        .order_by(models.StockPrice.recorded_at.desc())
        .first()
    )
    if current_price is None and latest_record:
        current_price = float(latest_record.price)

    if not dividend_yield or not current_price or dividend_yield <= 0 or current_price <= 0:
        return {
            "symbol": symbol.upper(),
            "available": False,
            "message": "Bu hisse için güncel temettü verimi bilgisi bulunamadı.",
        }

    target_annual_income = target_monthly_income * 12
    annual_dividend_per_share = current_price * dividend_yield
    required_shares = math.ceil(target_annual_income / annual_dividend_per_share)
    required_lots = math.ceil(required_shares / 1)  # BİST'te 1 lot = 1 pay (post-2015 uygulama)
    required_capital = round(required_shares * current_price, 2)

    return {
        "symbol": symbol.upper(),
        "available": True,
        "current_price": round(current_price, 2),
        "dividend_yield_pct": round(dividend_yield * 100, 2),
        "target_monthly_income": target_monthly_income,
        "required_shares": required_shares,
        "required_lots": required_lots,
        "required_capital": required_capital,
    }


# ---------------------------------------------------------------------------
# TASK: calculate_dca_backtest(symbol, monthly_amount, months)
# ---------------------------------------------------------------------------
def calculate_dca_backtest(db: Session, symbol: str, monthly_amount: float, months: int) -> Optional[Dict[str, Any]]:
    """
    Düzenli (her ay sabit tutar) yatırım stratejisinin (Dollar-Cost Averaging)
    geçmiş fiyat verisi üzerinden simülasyonunu yapar.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return None

    try:
        history = yf.Ticker(f"{symbol.upper()}.IS").history(period=f"{months + 1}mo", interval="1mo")
    except Exception as e:
        print(f"[AnalysisEngine] DCA geçmiş veri hatası ({symbol}): {e}")
        history = None

    if history is None or history.empty:
        return {
            "symbol": symbol.upper(),
            "available": False,
            "message": "Geriye dönük test için yeterli tarihsel veri bulunamadı.",
        }

    history = history.tail(months)
    total_invested = 0.0
    total_shares = 0.0
    timeline = []

    for idx, row in history.iterrows():
        price = float(row["Close"])
        if price <= 0:
            continue
        shares_bought = monthly_amount / price
        total_shares += shares_bought
        total_invested += monthly_amount
        current_value = total_shares * price
        timeline.append({
            "date": idx.strftime("%Y-%m-%d"),
            "price": round(price, 2),
            "invested_cumulative": round(total_invested, 2),
            "portfolio_value": round(current_value, 2),
        })

    if not timeline:
        return {"symbol": symbol.upper(), "available": False, "message": "Hesaplama için yeterli veri yok."}

    final_price = timeline[-1]["price"]
    final_value = round(total_shares * final_price, 2)
    profit = round(final_value - total_invested, 2)
    profit_pct = round((profit / total_invested) * 100, 2) if total_invested > 0 else 0.0

    return {
        "symbol": symbol.upper(),
        "available": True,
        "months": len(timeline),
        "monthly_amount": monthly_amount,
        "total_invested": round(total_invested, 2),
        "total_shares": round(total_shares, 4),
        "final_value": final_value,
        "profit": profit,
        "profit_pct": profit_pct,
        "timeline": timeline,
    }


# ---------------------------------------------------------------------------
# TASK: cleanup_old_logs() — user_logs tablosunu 90 günden eski kayıtlardan arındırır
# (scheduler.py içindeki log_cleanup_job ile aynı işi yapar; ham SQL örneği olarak sunulur)
# ---------------------------------------------------------------------------
def cleanup_old_logs(engine) -> int:
    with engine.connect() as conn:
        result = conn.execute(text("DELETE FROM user_logs WHERE created_at < datetime('now', '-90 days')"))
        conn.commit()
        return result.rowcount
