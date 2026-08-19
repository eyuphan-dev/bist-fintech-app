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
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import yfinance as yf
from sqlalchemy import text
from sqlalchemy.orm import Session

import models
from yf_retry import call_with_retry


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
        financials = call_with_retry(lambda: ticker.financials, attempts=2, label="financials")
        balance_sheet = call_with_retry(lambda: ticker.balance_sheet, attempts=2, label="balance_sheet")
        cashflow = call_with_retry(lambda: ticker.cashflow, attempts=2, label="cashflow")

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


def _net_fx_position(info: Dict[str, Any]) -> str:
    """
    Net döviz pozisyonu için kaba (heuristik) bir sınıflandırma: ihracat ağırlıklı
    sektörler döviz gelirine sahip olduğundan "POZITIF" (kur artışından olumlu
    etkilenme eğilimi), aksi halde "NOTR" varsayılır. Gerçek bilanço bazlı döviz
    varlık/yükümlülük ayrımı yfinance'ta yoktur; bu nedenle _fx_exposure_text ile
    aynı sektör/endüstri heuristiğini paylaşır.
    """
    sector = (info.get("sector") or "").lower()
    industry = (info.get("industry") or "").lower()
    export_heavy = any(k in industry or k in sector for k in ["textile", "auto", "steel", "chemical", "airlines", "tekstil", "otomotiv"])
    if export_heavy:
        return "POZITIF"
    total_debt = _safe_float(info.get("totalDebt"))
    total_cash = _safe_float(info.get("totalCash"))
    if total_debt is not None and total_cash is not None and (total_debt - total_cash) > 0:
        return "NEGATIF"
    return "NOTR"


def _calculate_debt_to_equity(info: Dict[str, Any], balance_sheet) -> Optional[float]:
    """Borç/Özkaynak oranı: önce yfinance info.debtToEquity (yüzde), yoksa bilançodan hesaplanır."""
    dte = _safe_float(info.get("debtToEquity"))
    if dte is not None:
        return round(dte / 100, 2) if dte > 10 else round(dte, 2)  # yfinance genelde yüzde olarak döner

    try:
        if balance_sheet is None or balance_sheet.empty:
            return None
        col = balance_sheet.columns[0]
        total_debt = _safe_float(balance_sheet.loc["Total Debt", col]) if "Total Debt" in balance_sheet.index else None
        equity = _safe_float(balance_sheet.loc["Stockholders Equity", col]) if "Stockholders Equity" in balance_sheet.index else None
        return round(_safe_div(total_debt, equity), 2) if _safe_div(total_debt, equity) is not None else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Altman Z-Skoru: finansal sıkıntı / iflas riski göstergesi
# Z = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
#   A = İşletme Sermayesi / Toplam Aktif
#   B = Dağıtılmamış Kârlar / Toplam Aktif
#   C = FVÖK (EBIT) / Toplam Aktif
#   D = Piyasa Değeri / Toplam Yükümlülük
#   E = Net Satışlar / Toplam Aktif
# Z > 2.99 → Güvenli (Safe) | 1.81 ≤ Z ≤ 2.99 → Gri Bölge (Grey) | Z < 1.81 → Sıkıntılı (Distress)
# ---------------------------------------------------------------------------
def _calculate_altman_z_score(ticker: yf.Ticker, info: Dict[str, Any]):
    try:
        balance_sheet = ticker.balance_sheet
        financials = ticker.financials
        if balance_sheet.empty or financials.empty:
            return None, None

        bs_col = balance_sheet.columns[0]
        fin_col = financials.columns[0]

        total_assets = _safe_float(balance_sheet.loc["Total Assets", bs_col]) if "Total Assets" in balance_sheet.index else None
        current_assets = _safe_float(balance_sheet.loc["Current Assets", bs_col]) if "Current Assets" in balance_sheet.index else None
        current_liab = _safe_float(balance_sheet.loc["Current Liabilities", bs_col]) if "Current Liabilities" in balance_sheet.index else None
        retained_earnings = _safe_float(balance_sheet.loc["Retained Earnings", bs_col]) if "Retained Earnings" in balance_sheet.index else None
        total_liab = _safe_float(balance_sheet.loc["Total Liabilities Net Minority Interest", bs_col]) if "Total Liabilities Net Minority Interest" in balance_sheet.index else None
        ebit = _safe_float(financials.loc["EBIT", fin_col]) if "EBIT" in financials.index else None
        revenue = _safe_float(financials.loc["Total Revenue", fin_col]) if "Total Revenue" in financials.index else None
        market_cap = _safe_float(info.get("marketCap"))

        if total_assets is None or total_assets == 0:
            return None, None

        working_capital = (current_assets - current_liab) if (current_assets is not None and current_liab is not None) else None

        a = _safe_div(working_capital, total_assets)
        b = _safe_div(retained_earnings, total_assets)
        c = _safe_div(ebit, total_assets)
        d = _safe_div(market_cap, total_liab)
        e = _safe_div(revenue, total_assets)

        components = [a, b, c, d, e]
        if all(v is None for v in components):
            return None, None

        # Eksik bileşen 0 kabul edilir (muhafazakâr yaklaşım — skor eksik veriyle şişirilmez)
        a, b, c, d, e = (v if v is not None else 0.0 for v in components)
        z = round(1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e, 2)

        if z > 2.99:
            zone = "SAFE"
        elif z >= 1.81:
            zone = "GREY"
        else:
            zone = "DISTRESS"

        return z, zone
    except Exception as e:
        print(f"[AnalysisEngine] Altman Z-Skoru hesaplama hatası: {e}")
        return None, None


def _analyst_consensus(ticker: yf.Ticker, info: Dict[str, Any], current_price: Optional[float]) -> Dict[str, Any]:
    """
    Aracı kurum hedef fiyat konsensüsü: yfinance'in info sözlüğündeki hedef fiyat
    alanları (targetMeanPrice/High/Low, numberOfAnalystOpinions, recommendationKey)
    ve ticker.recommendations tablosundaki en güncel ('0m') Al/Tut/Sat dağılımı
    kullanılır. BİST hisselerinin bir kısmında analist takibi olmadığından alanlar
    None kalabilir — bu durumda ilgili kart frontend'de "veri yok" gösterir.
    """
    target_mean = _safe_float(info.get("targetMeanPrice"))
    target_high = _safe_float(info.get("targetHighPrice"))
    target_low = _safe_float(info.get("targetLowPrice"))
    number_of_analysts = info.get("numberOfAnalystOpinions")
    recommendation_key = info.get("recommendationKey")

    upside_pct = None
    if target_mean is not None and current_price and current_price > 0:
        upside_pct = round(((target_mean - current_price) / current_price) * 100, 2)

    buy_count = hold_count = sell_count = None
    try:
        rec = call_with_retry(lambda: ticker.recommendations, attempts=2, label="recommendations")
        if rec is not None and not rec.empty and "period" in rec.columns:
            row = rec[rec["period"] == "0m"]
            if not row.empty:
                r = row.iloc[0]
                buy_count = int(r.get("strongBuy", 0) or 0) + int(r.get("buy", 0) or 0)
                hold_count = int(r.get("hold", 0) or 0)
                sell_count = int(r.get("sell", 0) or 0) + int(r.get("strongSell", 0) or 0)
    except Exception as e:
        print(f"[AnalysisEngine] Analist tavsiye dağılımı çekme hatası: {e}")

    return {
        "target_mean_price": target_mean,
        "target_high_price": target_high,
        "target_low_price": target_low,
        "target_upside_pct": upside_pct,
        "number_of_analysts": int(number_of_analysts) if number_of_analysts is not None else None,
        "recommendation_key": recommendation_key,
        "analyst_buy_count": buy_count,
        "analyst_hold_count": hold_count,
        "analyst_sell_count": sell_count,
    }


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

    existing_analysis = db.query(models.CompanyAnalysis).filter_by(stock_id=stock.id).first()

    yahoo_symbol = f"{symbol.upper()}.IS"
    try:
        ticker = yf.Ticker(yahoo_symbol)
        info = call_with_retry(lambda: ticker.info or {}, label=f"{symbol}.info")
    except Exception as e:
        print(f"[AnalysisEngine] yfinance bilgi çekme hatası ({symbol}): {e}")
        # Yahoo Finance sunucu IP'sini geçici/kalıcı olarak engellemiş olabilir
        # (retry ile de düzelmeyen bir durum). Elde daha önce hesaplanmış bir
        # analiz varsa kullanıcıya hata yerine son bilinen veriyi göster —
        # boş ekran/kırmızı hata banner'ı yerine "eski ama var olan" veri.
        if existing_analysis:
            print(f"[AnalysisEngine] {symbol}: canlı veri alınamadı, son bilinen analiz döndürülüyor (updated_at={existing_analysis.updated_at}).")
            return existing_analysis
        raise AnalysisFetchError(
            f"{symbol.upper()} için yfinance'tan veri alınamadı. Ağ bağlantısını veya sembolü kontrol edin. Detay: {e}"
        ) from e

    if not info or (info.get("regularMarketPrice") is None and info.get("currentPrice") is None and info.get("previousClose") is None):
        if existing_analysis:
            print(f"[AnalysisEngine] {symbol}: yfinance boş yanıt döndürdü, son bilinen analiz döndürülüyor (updated_at={existing_analysis.updated_at}).")
            return existing_analysis
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

    altman_z, altman_zone = _calculate_altman_z_score(ticker, info)
    debt_to_equity = _calculate_debt_to_equity(info, ticker.balance_sheet if hasattr(ticker, "balance_sheet") else None)
    net_fx_position = _net_fx_position(info)
    analyst_consensus = _analyst_consensus(ticker, info, current_price)

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
    analysis.altman_z_score = altman_z
    analysis.altman_zone = altman_zone
    analysis.debt_to_equity = debt_to_equity
    analysis.net_fx_position = net_fx_position
    # Temettü: yfinance dividendYield oransal gelir (0.05 = %5); yüzdeye çevrilir.
    # Bazı sembollerde alan yüzde olarak (5.0) gelebildiği için 1'den büyük
    # değerler zaten yüzde kabul edilir — aksi halde %500 gibi saçma bir verim çıkardı.
    _dy = _safe_float(info.get("dividendYield"))
    if _dy is not None and _dy > 0:
        analysis.dividend_yield = round(_dy * 100, 2) if _dy <= 1 else round(_dy, 2)
    else:
        analysis.dividend_yield = None
    analysis.dividend_rate = _safe_float(info.get("dividendRate"))
    _ldd = info.get("lastDividendDate")
    if _ldd:
        try:
            from datetime import datetime as _dt
            analysis.last_dividend_date = _dt.utcfromtimestamp(int(_ldd)).date()
        except Exception:
            analysis.last_dividend_date = None
    analysis.target_mean_price = analyst_consensus["target_mean_price"]
    analysis.target_high_price = analyst_consensus["target_high_price"]
    analysis.target_low_price = analyst_consensus["target_low_price"]
    analysis.target_upside_pct = analyst_consensus["target_upside_pct"]
    analysis.number_of_analysts = analyst_consensus["number_of_analysts"]
    analysis.recommendation_key = analyst_consensus["recommendation_key"]
    analysis.analyst_buy_count = analyst_consensus["analyst_buy_count"]
    analysis.analyst_hold_count = analyst_consensus["analyst_hold_count"]
    analysis.analyst_sell_count = analyst_consensus["analyst_sell_count"]
    analysis.updated_at = datetime.utcnow()

    # Yabancı/kurumsal sahiplik oranı anlık görüntüsü (30/90 günlük trend için) —
    # günde birden fazla tazelemede tekrar kayıt oluşturmamak için aynı gün kontrolü yapılır.
    held_pct = _safe_float(info.get("heldPercentInstitutions"))
    if held_pct is not None:
        today = datetime.utcnow().date()
        already_today = (
            db.query(models.ForeignHoldingSnapshot)
            .filter(
                models.ForeignHoldingSnapshot.stock_id == stock.id,
                models.ForeignHoldingSnapshot.recorded_at >= datetime(today.year, today.month, today.day),
            )
            .first()
        )
        if not already_today:
            db.add(models.ForeignHoldingSnapshot(
                stock_id=stock.id,
                held_pct=round(held_pct * 100, 2),
                recorded_at=datetime.utcnow(),
            ))

    db.commit()
    db.refresh(analysis)
    print(f"[AnalysisEngine] {symbol}: Piotroski={piotroski}, F/K={pe_ratio}, Makul Değer={fair_value}, Altman Z={altman_z}")
    return analysis


# ---------------------------------------------------------------------------
# TASK: calculate_pivot_levels(symbol) — Klasik Pivot Noktaları + Fibonacci Seviyeleri
# ---------------------------------------------------------------------------
def calculate_pivot_levels(symbol: str) -> Dict[str, Any]:
    """
    Bir önceki tam işlem gününün Yüksek/Düşük/Kapanış (High/Low/Close) verisinden
    klasik pivot noktalarını (P, R1-R3, S1-S3) ve son 20 günlük yüksek/düşük
    aralığına göre Fibonacci geri çekilme seviyelerini (%23.6/%38.2/%50/%61.8) hesaplar.
    """
    yahoo_symbol = f"{symbol.upper()}.IS"
    try:
        history = call_with_retry(
            lambda: yf.Ticker(yahoo_symbol).history(period="1mo", interval="1d"),
            attempts=2, label=f"{symbol}.pivot_history",
        )
    except Exception as e:
        print(f"[AnalysisEngine] Pivot seviyeleri için geçmiş veri hatası ({symbol}): {e}")
        history = None

    if history is None or history.empty or len(history) < 2:
        return {
            "symbol": symbol.upper(),
            "available": False,
            "message": "Pivot/Fibonacci seviyeleri için yeterli geçmiş fiyat verisi bulunamadı.",
        }

    last_row = history.iloc[-1]
    prev_high = _safe_float(last_row["High"])
    prev_low = _safe_float(last_row["Low"])
    prev_close = _safe_float(last_row["Close"])

    if prev_high is None or prev_low is None or prev_close is None:
        return {
            "symbol": symbol.upper(),
            "available": False,
            "message": "Pivot seviyeleri için geçerli Yüksek/Düşük/Kapanış verisi bulunamadı.",
        }

    pivot = round((prev_high + prev_low + prev_close) / 3, 2)
    r1 = round((2 * pivot) - prev_low, 2)
    s1 = round((2 * pivot) - prev_high, 2)
    r2 = round(pivot + (prev_high - prev_low), 2)
    s2 = round(pivot - (prev_high - prev_low), 2)
    r3 = round(prev_high + 2 * (pivot - prev_low), 2)
    s3 = round(prev_low - 2 * (prev_high - pivot), 2)

    # Fibonacci geri çekilme: son 20 günlük (mevcut) yüksek/düşük aralığı baz alınır
    range_window = history.tail(20)
    swing_high = _safe_float(range_window["High"].max())
    swing_low = _safe_float(range_window["Low"].min())

    fib_236 = fib_382 = fib_500 = fib_618 = None
    if swing_high is not None and swing_low is not None and swing_high > swing_low:
        diff = swing_high - swing_low
        fib_236 = round(swing_high - diff * 0.236, 2)
        fib_382 = round(swing_high - diff * 0.382, 2)
        fib_500 = round(swing_high - diff * 0.5, 2)
        fib_618 = round(swing_high - diff * 0.618, 2)

    return {
        "symbol": symbol.upper(),
        "as_of_date": history.index[-1].strftime("%Y-%m-%d"),
        "previous_close": prev_close,
        "pivot": pivot,
        "r1": r1, "r2": r2, "r3": r3,
        "s1": s1, "s2": s2, "s3": s3,
        "fib_236": fib_236, "fib_382": fib_382, "fib_500": fib_500, "fib_618": fib_618,
        "available": True,
        "message": None,
    }


# ---------------------------------------------------------------------------
# TASK: get_foreign_holding_trend(db, stock_id) — 30/90 günlük yabancı/kurumsal
# sahiplik oranı değişimi (en yakın kayıtlı anlık görüntülere göre)
# ---------------------------------------------------------------------------
def get_foreign_holding_trend(db: Session, symbol: str) -> Dict[str, Any]:
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return {"symbol": symbol.upper(), "available": False, "message": "Hisse bulunamadı."}

    snapshots = (
        db.query(models.ForeignHoldingSnapshot)
        .filter_by(stock_id=stock.id)
        .order_by(models.ForeignHoldingSnapshot.recorded_at.asc())
        .all()
    )
    if not snapshots:
        return {
            "symbol": symbol.upper(),
            "available": False,
            "message": "Yabancı/kurumsal sahiplik oranı için henüz veri toplanmadı. Analiz her tazelendiğinde bir anlık görüntü kaydedilir; trend için birkaç günlük veri birikmesi gerekir.",
        }

    current = snapshots[-1]
    now = current.recorded_at

    def _closest_before(days: int):
        target = now - timedelta(days=days)
        candidates = [s for s in snapshots if s.recorded_at <= target]
        return candidates[-1] if candidates else None

    ref_30 = _closest_before(30)
    ref_90 = _closest_before(90)

    change_30d = round(float(current.held_pct) - float(ref_30.held_pct), 2) if ref_30 else None
    change_90d = round(float(current.held_pct) - float(ref_90.held_pct), 2) if ref_90 else None

    message = None
    if change_30d is None and change_90d is None:
        message = "30/90 günlük trend için henüz yeterli geçmiş veri birikmedi (yalnızca güncel oran mevcut)."

    return {
        "symbol": symbol.upper(),
        "current_pct": float(current.held_pct),
        "change_30d": change_30d,
        "change_90d": change_90d,
        "available": True,
        "message": message,
    }


def _next_earnings_date(ticker: yf.Ticker) -> Optional[Any]:
    """
    yfinance ticker.calendar()'daki 'Earnings Date' listesinden bugünden sonraki en
    yakın tarihi döner. ticker.calendar hafif bir çağrıdır (financials/balance_sheet
    çekmez), bu yüzden tüm hisseler için günlük toplu taramada kullanılabilir.
    """
    try:
        calendar = ticker.calendar
        if not calendar:
            return None
        earnings_dates = calendar.get("Earnings Date")
        if not earnings_dates:
            return None
        today = datetime.utcnow().date()
        future_dates = [d for d in earnings_dates if d and d >= today]
        return min(future_dates) if future_dates else None
    except Exception:
        return None


def refresh_earnings_calendar(db: Session) -> int:
    """
    Aktif hisselerin bir sonraki bilanço açıklama tarihini (varsa) yfinance'tan
    hafif bir çağrıyla çekip company_analysis.next_earnings_date alanına yazar.
    Diğer derin analiz alanlarına (Piotroski, F/K vb.) dokunmaz — CompanyAnalysis
    kaydı yoksa yalnızca bu alan için oluşturulur. Scheduler tarafından günlük
    çağrılır; kaç hissenin güncellendiğini döner.
    """
    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    updated = 0
    for i, stock in enumerate(stocks):
        if i > 0:
            time.sleep(0.4)
        try:
            ticker = yf.Ticker(f"{stock.symbol}.IS")
            next_date = _next_earnings_date(ticker)
        except Exception as e:
            print(f"[AnalysisEngine] Bilanço takvimi çekme hatası ({stock.symbol}): {e}")
            continue

        analysis = db.query(models.CompanyAnalysis).filter_by(stock_id=stock.id).first()
        if not analysis:
            analysis = models.CompanyAnalysis(stock_id=stock.id)
            db.add(analysis)
        analysis.next_earnings_date = next_date
        updated += 1

    db.commit()
    return updated


def calculate_sector_pe_averages(db: Session) -> Dict[int, float]:
    """Aktif hisseler için F/K oranlarını çekip basit ortalama (piyasa geneli) döner."""
    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    pe_values: List[float] = []
    for i, stock in enumerate(stocks):
        if i > 0:
            time.sleep(0.4)
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
        info = call_with_retry(
            lambda: yf.Ticker(f"{symbol.upper()}.IS").info or {},
            attempts=2, label=f"{symbol}.dividend_info",
        )
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
        history = call_with_retry(
            lambda: yf.Ticker(f"{symbol.upper()}.IS").history(period=f"{months + 1}mo", interval="1mo"),
            attempts=2, label=f"{symbol}.dca_history",
        )
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
# (scheduler.py içindeki log_cleanup_job ile aynı işi yapar)
# ---------------------------------------------------------------------------
def cleanup_old_logs(engine) -> int:
    """
    Python tarafında hesaplanan mutlak kesme tarihiyle (SQLite'a özgü
    datetime('now', '-90 days') fonksiyonu yerine) çalışır — bu yüzden hem
    SQLite hem Postgres'te sorunsuz çalışır.
    """
    cutoff = datetime.utcnow() - timedelta(days=90)
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM user_logs WHERE created_at < :cutoff"),
            {"cutoff": cutoff},
        )
        conn.commit()
        return result.rowcount
