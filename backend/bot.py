import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, EMAIndicator

import models
from cache import get_latest_price
from market_hours import is_market_open

# ---------------------------------------------------------------------------
# Süre & Zaman Dilimi Bazlı Strateji Motoru
# ---------------------------------------------------------------------------
# '1D' Gün İçi/Scalp : Ham (5-15 dk) fiyat verisi, hızlı RSI(7) + EMA9/EMA21 momentum,
#                       dar Stop-Loss/Take-Profit. Süre dolunca pozisyonlar kapatılır.
# '1W' Haftalık/Swing: ~4 barlık (saatlik benzeri) yeniden örneklenmiş veri, MACD kesişimi +
#                       destek/direnç (rolling min/max) kırılımı, orta Stop-Loss/Take-Profit.
# '1M' Aylık/Trend    : Günlük kapanışlara yeniden örneklenmiş veri, SMA20/SMA50 trend kesişimi
#                       + Piotroski skoru güvenlik barajı, geniş Stop-Loss/Take-Profit.
BOT_STRATEGY_CONFIG = {
    "1D": {
        "label": "1 Günlük (Gün İçi / Scalp)",
        "duration": timedelta(days=1),
        "mode": "scalp",
        "lookback": 60,
        "resample_every": 1,
        "rsi_period": 7,
        "ema_short": 9,
        "ema_long": 21,
        "stop_loss_pct": 1.5,
        "take_profit_pct": 3.0,
    },
    "1W": {
        "label": "1 Haftalık (Swing Trade)",
        "duration": timedelta(weeks=1),
        "mode": "swing",
        "lookback": 240,
        "resample_every": 4,   # ~4 ham barı 1 "saatlik" bar gibi birleştirir
        "rsi_period": 14,
        "breakout_window": 20,
        "stop_loss_pct": 4.0,
        "take_profit_pct": 8.0,
    },
    "1M": {
        "label": "1 Aylık (Trend / Orta Vadeli)",
        "duration": timedelta(days=30),
        "mode": "trend",
        "lookback": 500,
        "resample_every": "daily",
        "sma_short": 20,
        "sma_long": 50,
        "min_piotroski_score": 5,  # Piotroski skoru bu değerin altındaysa AL sinyali reddedilir
        "stop_loss_pct": 7.0,
        "take_profit_pct": 15.0,
    },
}

DEFAULT_TIME_FRAME = "1D"


def get_strategy_config(time_frame: str) -> dict:
    return BOT_STRATEGY_CONFIG.get(time_frame, BOT_STRATEGY_CONFIG[DEFAULT_TIME_FRAME])


# ---------------------------------------------------------------------------
# Risk Modu — Sinyal Güven Eşiği + Stop-Loss/Take-Profit Ölçeklendirme
# ---------------------------------------------------------------------------
# time_frame (1D/1W/1M) sinyalin YÖNÜNÜ (AL/SAT) ve veri çözünürlüğünü belirler;
# risk_mode ise o sinyale ne kadar güvenildiğinde işleme girileceğini (min_confidence)
# ve pozisyon risk büyüklüğünü (stop_loss_pct/take_profit_pct) belirler. İkisi
# birbirinden bağımsız, birlikte çalışan iki eksendir.
RISK_MODE_CONFIG = {
    "slow": {
        "label": "🐢 Yavaş (Muhafazakâr)",
        "min_confidence": 0.80,
        "stop_loss_pct": 2.5,
        "take_profit_pct": 5.0,
    },
    "normal": {
        "label": "⚖️ Normal (Dengeli)",
        "min_confidence": 0.65,
        "stop_loss_pct": 4.5,
        "take_profit_pct": 9.0,
    },
    "aggressive": {
        "label": "🚀 Agresif (Yüksek Risk)",
        "min_confidence": 0.52,
        "stop_loss_pct": 8.0,
        "take_profit_pct": 16.0,
    },
}

DEFAULT_RISK_MODE = "normal"

# Eski (Türkçe) risk_profile değerleri ile geriye dönük uyumluluk
_LEGACY_RISK_MODE_MAP = {"dusuk": "slow", "dengeli": "normal", "yuksek": "aggressive"}


def get_risk_mode_config(risk_mode: Optional[str]) -> dict:
    normalized = _LEGACY_RISK_MODE_MAP.get(risk_mode, risk_mode)
    return RISK_MODE_CONFIG.get(normalized, RISK_MODE_CONFIG[DEFAULT_RISK_MODE])


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Genel (zaman dilimi bağımsız) teknik indikatör hesaplayıcı — hisse detay sayfasındaki
    RSI(14)/MACD/SMA(5,20)/Bollinger göstergeleri için kullanılır.
    """
    if len(df) < 5:
        df["rsi"] = 50.0
        df["macd"] = 0.0
        df["macd_signal"] = 0.0
        df["sma_short"] = df["price"]
        df["sma_long"] = df["price"]
        df["bb_high"] = df["price"]
        df["bb_low"] = df["price"]
        return df

    rsi_period = min(14, len(df) - 1)
    df["rsi"] = RSIIndicator(close=df["price"], window=rsi_period).rsi().fillna(50.0)

    macd = MACD(close=df["price"])
    df["macd"] = macd.macd().fillna(0.0)
    df["macd_signal"] = macd.macd_signal().fillna(0.0)

    df["sma_short"] = SMAIndicator(close=df["price"], window=min(5, len(df))).sma_indicator().fillna(df["price"])
    df["sma_long"] = SMAIndicator(close=df["price"], window=min(20, len(df))).sma_indicator().fillna(df["price"])

    from ta.volatility import BollingerBands
    bb = BollingerBands(close=df["price"], window=min(20, len(df)))
    df["bb_high"] = bb.bollinger_hband().fillna(df["price"])
    df["bb_low"] = bb.bollinger_lband().fillna(df["price"])

    return df


def train_and_predict_ml(df: pd.DataFrame) -> str:
    """Genel amaçlı (legacy) RSI/MACD/Bollinger tabanlı basit kural motoru + Random Forest fallback'i."""
    from sklearn.ensemble import RandomForestClassifier

    if len(df) < 15:
        last_row = df.iloc[-1]
        rsi = last_row["rsi"]
        macd = last_row["macd"]
        macd_sig = last_row["macd_signal"]
        price = last_row["price"]
        bb_low = last_row["bb_low"]
        bb_high = last_row["bb_high"]

        if rsi < 30 or (macd > macd_sig and price <= bb_low * 1.02):
            return "AL"
        elif rsi > 70 or (macd < macd_sig and price >= bb_high * 0.98):
            return "SAT"
        else:
            return "BEKLE"

    df_features = pd.DataFrame()
    df_features["rsi"] = df["rsi"]
    df_features["macd_diff"] = df["macd"] - df["macd_signal"]
    df_features["sma_ratio"] = df["price"] / df["sma_short"]
    df_features["bb_ratio"] = (df["price"] - df["bb_low"]) / (df["bb_high"] - df["bb_low"] + 1e-5)

    price_pct_change = df["price"].pct_change().shift(-1)
    target = np.where(price_pct_change > 0.005, 1, np.where(price_pct_change < -0.005, -1, 0))
    df_features["target"] = target

    train_data = df_features.dropna()
    if len(train_data) < 5:
        last_row = df.iloc[-1]
        if last_row["rsi"] < 32:
            return "AL"
        elif last_row["rsi"] > 68:
            return "SAT"
        return "BEKLE"

    X = train_data.drop(columns=["target"])
    y = train_data["target"]
    clf = RandomForestClassifier(n_estimators=10, random_state=42)
    clf.fit(X, y)

    current_features = df_features.drop(columns=["target"]).iloc[[-1]]
    pred = clf.predict(current_features)[0]

    if pred == 1:
        return "AL"
    elif pred == -1:
        return "SAT"
    return "BEKLE"


# ---------------------------------------------------------------------------
# Zaman dilimine göre yeniden örnekleme (resample) + sinyal üretimi
# ---------------------------------------------------------------------------
def _resample_price_records(price_records, config: dict) -> pd.DataFrame:
    data = {
        "price": [float(p.price) for p in price_records],
        "recorded_at": [p.recorded_at for p in price_records],
    }
    df = pd.DataFrame(data)

    resample_every = config["resample_every"]
    if resample_every == "daily":
        df["date"] = df["recorded_at"].apply(lambda d: d.date())
        df = df.groupby("date", as_index=False).agg({"price": "last", "recorded_at": "last"})
    elif isinstance(resample_every, int) and resample_every > 1:
        df = df.iloc[::resample_every].reset_index(drop=True)

    return df.tail(config["lookback"]).reset_index(drop=True)


def _generate_scalp_signal(df: pd.DataFrame, config: dict) -> tuple:
    if len(df) < 5:
        return "BEKLE", 0.0
    rsi_period = min(config["rsi_period"], len(df) - 1)
    rsi = RSIIndicator(close=df["price"], window=rsi_period).rsi().fillna(50.0)
    ema_short = EMAIndicator(close=df["price"], window=min(config["ema_short"], len(df))).ema_indicator().fillna(df["price"])
    ema_long = EMAIndicator(close=df["price"], window=min(config["ema_long"], len(df))).ema_indicator().fillna(df["price"])

    last_rsi = float(rsi.iloc[-1])
    last_ema_short = float(ema_short.iloc[-1])
    last_ema_long = float(ema_long.iloc[-1])
    ema_cross_up = last_ema_short > last_ema_long

    # Güven skoru: RSI'nin aşırı alım/satım eşiğinden ne kadar uzaklaştığı +
    # EMA9/EMA21 arasındaki farkın fiyata oranı (momentumun gücü)
    rsi_strength = _clip01(abs(50.0 - last_rsi) / 50.0)
    ema_gap_ratio = abs(last_ema_short - last_ema_long) / last_ema_long if last_ema_long else 0.0
    ema_strength = _clip01(ema_gap_ratio / 0.03)
    confidence = 0.5 * rsi_strength + 0.5 * ema_strength

    if last_rsi < 30 and ema_cross_up:
        return "AL", confidence
    if last_rsi > 70 and not ema_cross_up:
        return "SAT", confidence
    return "BEKLE", confidence


def _generate_swing_signal(df: pd.DataFrame, config: dict) -> tuple:
    if len(df) < 10:
        return "BEKLE", 0.0
    macd = MACD(close=df["price"])
    macd_line = macd.macd().fillna(0.0)
    macd_signal = macd.macd_signal().fillna(0.0)

    window = min(config["breakout_window"], len(df))
    rolling_high = df["price"].rolling(window=window).max()
    rolling_low = df["price"].rolling(window=window).min()

    last_price = float(df["price"].iloc[-1])
    last_macd = float(macd_line.iloc[-1])
    last_macd_signal = float(macd_signal.iloc[-1])
    macd_cross_up = last_macd > last_macd_signal
    last_high = float(rolling_high.iloc[-1])
    last_low = float(rolling_low.iloc[-1])
    breakout_up = last_price >= last_high * 0.995
    breakdown = last_price <= last_low * 1.005

    # Güven skoru: MACD histogramının fiyata oranı (kesişimin gücü) +
    # kırılımın destek/direnç seviyesini ne kadar aştığı
    macd_strength = _clip01(abs(last_macd - last_macd_signal) / (last_price * 0.01)) if last_price else 0.0
    if breakout_up and last_high:
        breakout_strength = _clip01((last_price - last_high) / (last_high * 0.02) + 0.5)
    elif breakdown and last_low:
        breakout_strength = _clip01((last_low - last_price) / (last_low * 0.02) + 0.5)
    else:
        breakout_strength = 0.3
    confidence = 0.5 * macd_strength + 0.5 * breakout_strength

    if macd_cross_up and breakout_up:
        return "AL", confidence
    if not macd_cross_up and breakdown:
        return "SAT", confidence
    return "BEKLE", confidence


def _generate_trend_signal(df: pd.DataFrame, config: dict, piotroski_score) -> tuple:
    if len(df) < 10:
        return "BEKLE", 0.0
    sma_short = SMAIndicator(close=df["price"], window=min(config["sma_short"], len(df))).sma_indicator().fillna(df["price"])
    sma_long = SMAIndicator(close=df["price"], window=min(config["sma_long"], len(df))).sma_indicator().fillna(df["price"])

    last_sma_short = float(sma_short.iloc[-1])
    last_sma_long = float(sma_long.iloc[-1])
    trend_up = last_sma_short > last_sma_long
    trend_down = last_sma_short < last_sma_long

    # Piotroski güvenlik barajı: skor biliniyorsa ve eşik altındaysa AL sinyali reddedilir
    piotroski_ok = piotroski_score is None or piotroski_score >= config["min_piotroski_score"]

    # Güven skoru: SMA20/SMA50 arasındaki farkın gücü + Piotroski skorunun (varsa) katkısı
    sma_gap_ratio = abs(last_sma_short - last_sma_long) / last_sma_long if last_sma_long else 0.0
    sma_strength = _clip01(sma_gap_ratio / 0.05)
    piotroski_strength = (piotroski_score / 9.0) if piotroski_score is not None else 0.5
    confidence = 0.6 * sma_strength + 0.4 * _clip01(piotroski_strength)

    if trend_up and piotroski_ok:
        return "AL", confidence
    if trend_down:
        return "SAT", confidence
    return "BEKLE", confidence


def _generate_timeframe_signal(price_records, config: dict, risk_config: dict, piotroski_score=None):
    """
    Zaman dilimine göre resample edilmiş veri üzerinden AL/SAT/BEKLE sinyali, son fiyat
    ve sinyal güven skorunu (confidence) döner. Sinyalin YÖNÜ zaman dilimi stratejisinden
    (scalp/swing/trend) gelir; ancak üretilen sinyal, risk_config'in min_confidence eşiğinin
    ALTINDAYSA işleme dönüştürülmeden "BEKLE"ye düşürülür (risk modu güven filtresi).
    """
    df = _resample_price_records(price_records, config)
    if df.empty:
        return "BEKLE", None, 0.0

    last_price = float(df["price"].iloc[-1])
    mode = config["mode"]

    if mode == "scalp":
        action, confidence = _generate_scalp_signal(df, config)
    elif mode == "swing":
        action, confidence = _generate_swing_signal(df, config)
    else:
        action, confidence = _generate_trend_signal(df, config, piotroski_score)

    if action != "BEKLE" and confidence < risk_config["min_confidence"]:
        action = "BEKLE"

    return action, last_price, confidence


def _check_stop_loss_take_profit(portfolio_entry, latest_price: float, risk_config: dict):
    """
    Pozisyonun Stop-Loss/Take-Profit eşiklerini aştığı durumda zorunlu SAT kararı ve
    gerekçesini döner. Eşikler risk_config'ten (risk moduna göre) gelir — zaman dilimi
    stratejisinden bağımsız olarak kullanıcının seçtiği risk moduna göre ölçeklenir.
    """
    avg_cost = float(portfolio_entry.average_cost)
    if avg_cost <= 0:
        return None
    change_pct = ((latest_price - avg_cost) / avg_cost) * 100

    if change_pct <= -risk_config["stop_loss_pct"]:
        return f"Stop-Loss tetiklendi (%{risk_config['stop_loss_pct']:.1f} zarar sınırı aşıldı, gerçekleşen: %{change_pct:.2f})."
    if change_pct >= risk_config["take_profit_pct"]:
        return f"Take-Profit hedefine ulaşıldı (%{risk_config['take_profit_pct']:.1f} kâr hedefi, gerçekleşen: %{change_pct:.2f})."
    return None


def _execute_bot_trading_cycle(
    db: Session,
    balance_holder,
    owner_user_id: int,
    is_bot_portfolio: bool,
    log_label: str,
    time_frame: str = DEFAULT_TIME_FRAME,
    risk_mode: str = DEFAULT_RISK_MODE,
    force_liquidate: bool = False,
):
    """
    Tek bir "bot aktörü" (paylaşımlı demo bot ya da bir kullanıcının kişisel botu)
    için, seçilen zaman dilimine (time_frame) uygun strateji motorunu, seçilen risk
    moduna (risk_mode) göre güven eşiği ve Stop-Loss/Take-Profit ile çalıştırır.

    force_liquidate=True verilirse (örn. bot süresi dolduğunda) sinyale bakılmaksızın
    tüm açık pozisyonlar piyasa fiyatından kapatılır.
    """
    config = get_strategy_config(time_frame)
    risk_config = get_risk_mode_config(risk_mode)
    stocks = db.query(models.Stock).filter_by(is_active=True).all()

    portfolio_rows = (
        db.query(models.Portfolio)
        .filter_by(user_id=owner_user_id, is_bot_portfolio=is_bot_portfolio)
        .all()
    )
    portfolio_map = {p.stock_id: p for p in portfolio_rows}
    stock_by_id = {s.id: s for s in stocks}

    for stock in stocks:
        price_records = db.query(models.StockPrice)\
            .filter_by(stock_id=stock.id)\
            .order_by(models.StockPrice.recorded_at.asc())\
            .limit(500)\
            .all()

        if not price_records:
            continue

        piotroski_score = None
        if config["mode"] == "trend":
            analysis = db.query(models.CompanyAnalysis).filter_by(stock_id=stock.id).first()
            if analysis and analysis.piotroski_score is not None:
                piotroski_score = int(analysis.piotroski_score)

        action, latest_price, confidence = _generate_timeframe_signal(price_records, config, risk_config, piotroski_score)
        if latest_price is None:
            continue

        portfolio_entry = portfolio_map.get(stock.id)

        # Süre dolduysa ya da harici bir tetikleyiciyle likidasyon isteniyorsa, elde pozisyon
        # varsa sinyale bakılmaksızın kapatılır.
        forced_reason = None
        if force_liquidate and portfolio_entry:
            forced_reason = f"Bot süresi ({config['label']}) doldu; açık pozisyon piyasa fiyatından kapatıldı."
        elif portfolio_entry:
            forced_reason = _check_stop_loss_take_profit(portfolio_entry, latest_price, risk_config)

        if forced_reason:
            action = "SAT"

        if action == "AL" and not force_liquidate:
            if not portfolio_entry:
                available_cash = float(balance_holder.virtual_balance)
                trade_allocation = available_cash * 0.15

                if trade_allocation >= 100.0:
                    quantity = round(trade_allocation / latest_price, 4)
                    if quantity > 0:
                        cost = quantity * latest_price
                        balance_holder.virtual_balance = float(balance_holder.virtual_balance) - cost

                        db.add(models.Portfolio(
                            user_id=owner_user_id,
                            stock_id=stock.id,
                            quantity=quantity,
                            average_cost=latest_price,
                            is_bot_portfolio=is_bot_portfolio,
                        ))

                        reason = (
                            f"[{config['label']} / {risk_config['label']}] Strateji AL sinyali verdi "
                            f"(Güven: %{confidence * 100:.0f}, Stop-Loss: %{risk_config['stop_loss_pct']}, "
                            f"Take-Profit: %{risk_config['take_profit_pct']})."
                        )
                        db.add(models.BotLog(
                            user_id=owner_user_id, stock_id=stock.id, action_type="AL",
                            price=latest_price, quantity=quantity, reason_text=reason
                        ))
                        print(f"{log_label} SATIN ALIM: {stock.symbol} - {quantity} adet @ {latest_price} TL")

        elif action == "SAT":
            if portfolio_entry:
                quantity = float(portfolio_entry.quantity)
                revenue = quantity * latest_price
                balance_holder.virtual_balance = float(balance_holder.virtual_balance) + revenue
                db.delete(portfolio_entry)

                profit_loss = (latest_price - float(portfolio_entry.average_cost)) / float(portfolio_entry.average_cost) * 100
                reason = forced_reason or (
                    f"[{config['label']} / {risk_config['label']}] Strateji SAT sinyali verdi "
                    f"(Güven: %{confidence * 100:.0f}). Kâr/Zarar: %{profit_loss:.2f}. Pozisyon kapatıldı."
                )
                if forced_reason:
                    reason = f"{forced_reason} Kâr/Zarar: %{profit_loss:.2f}."

                db.add(models.BotLog(
                    user_id=owner_user_id, stock_id=stock.id, action_type="SAT",
                    price=latest_price, quantity=quantity, reason_text=reason
                ))
                print(f"{log_label} SATIŞ: {stock.symbol} - {quantity} adet @ {latest_price} TL. Kâr/Zarar: %{profit_loss:.2f}")

    db.commit()

    total_stock_value = 0.0
    updated_portfolios = (
        db.query(models.Portfolio)
        .filter_by(user_id=owner_user_id, is_bot_portfolio=is_bot_portfolio)
        .all()
    )
    for item in updated_portfolios:
        latest_record = db.query(models.StockPrice)\
            .filter_by(stock_id=item.stock_id)\
            .order_by(models.StockPrice.recorded_at.desc())\
            .first()
        if latest_record:
            total_stock_value += float(item.quantity) * float(latest_record.price)

    current_date = date.today()
    total_portfolio_value = float(balance_holder.virtual_balance) + total_stock_value

    perf_record = db.query(models.BotPerformanceHistory).filter_by(
        user_id=owner_user_id, recorded_date=current_date
    ).first()
    if perf_record:
        perf_record.total_portfolio_value = total_portfolio_value
    else:
        db.add(models.BotPerformanceHistory(
            user_id=owner_user_id, total_portfolio_value=total_portfolio_value, recorded_date=current_date
        ))

    db.commit()
    print(f"{log_label} Güncel Portföy Değeri: {total_portfolio_value:.2f} TL "
          f"(Nakit: {float(balance_holder.virtual_balance):.2f} TL, Hisseler: {total_stock_value:.2f} TL)")


def run_ai_bot_simulation(db: Session):
    """Paylaşımlı demo bot ('yapay_zeka_trader' kullanıcısı) — geriye dönük uyumluluk için korunur."""
    open_flag, reason = is_market_open()
    if not open_flag:
        print(f"[AI Bot] Simülasyon atlandı — {reason}")
        return

    print("[AI Bot] Yapay Zeka Trader (paylaşımlı demo bot) simülasyonu başlatılıyor...")

    bot_user = db.query(models.User).filter_by(is_bot=True).first()
    if not bot_user:
        print("[AI Bot] Hata: Veritabanında Yapay Zeka Trader kullanıcısı bulunamadı!")
        return

    _execute_bot_trading_cycle(
        db, balance_holder=bot_user, owner_user_id=bot_user.id,
        is_bot_portfolio=False, log_label="[AI Bot]", time_frame="1D",
    )


def _check_and_apply_expiry(db: Session, user_bot: "models.UserBot") -> bool:
    """
    ends_at geçmişse: açık pozisyonları piyasa fiyatından kapatır, botu pasif hale getirir.
    Döner: True ise bot bu döngüde normal şekilde işlem yapmaya devam edebilir.
    """
    if not user_bot.ends_at or datetime.utcnow() < user_bot.ends_at:
        return True

    config = get_strategy_config(user_bot.time_frame or DEFAULT_TIME_FRAME)
    print(f"[Quant Bot] Kullanıcı #{user_bot.user_id} botunun süresi doldu ({config['label']}). Pozisyonlar kapatılıyor ve bot pasife alınıyor.")

    _execute_bot_trading_cycle(
        db, balance_holder=user_bot, owner_user_id=user_bot.user_id,
        is_bot_portfolio=True, log_label=f"[Kişisel Bot #{user_bot.user_id} - Süre Doldu]",
        time_frame=user_bot.time_frame or DEFAULT_TIME_FRAME,
        risk_mode=user_bot.risk_profile or DEFAULT_RISK_MODE, force_liquidate=True,
    )

    user_bot.is_active = False
    db.add(models.UserLog(
        user_id=user_bot.user_id,
        action="BOT_EXPIRED",
        details=f"Kişisel AI Bot süresi ({config['label']}) doldu, otomatik olarak durduruldu.",
    ))
    db.commit()
    return False


def run_quant_bot(db: Session):
    """
    Çok Kullanıcılı Kişisel AI Bot çalıştırıcısı.

    Piyasa açıksa, her aktif UserBot için:
      1. Süresi dolmuş mu kontrol edilir (dolmuşsa pozisyonlar kapatılır, bot pasife alınır).
      2. Süresi devam ediyorsa, kendi time_frame'ine uygun strateji (scalp/swing/trend)
         BAĞIMSIZ olarak, kendi sanal bakiyesiyle çalıştırılır.
    Paylaşımlı topluluk demo botu artık çalıştırılmaz — yalnızca kişisel botlar aktiftir.
    """
    open_flag, reason = is_market_open()
    if not open_flag:
        print(f"[Quant Bot] Çalıştırılmadı: {reason}")
        return

    user_bots = db.query(models.UserBot).filter_by(is_active=True).all()
    print(f"[Quant Bot] {len(user_bots)} aktif kişisel bot için işlem döngüsü başlatılıyor...")

    for user_bot in user_bots:
        try:
            still_active = _check_and_apply_expiry(db, user_bot)
            if not still_active:
                continue

            _execute_bot_trading_cycle(
                db, balance_holder=user_bot, owner_user_id=user_bot.user_id,
                is_bot_portfolio=True, log_label=f"[Kişisel Bot #{user_bot.user_id}]",
                time_frame=user_bot.time_frame or DEFAULT_TIME_FRAME,
                risk_mode=user_bot.risk_profile or DEFAULT_RISK_MODE,
            )
        except Exception as e:
            print(f"[Quant Bot] Kullanıcı #{user_bot.user_id} botu çalıştırılırken hata: {e}")
            db.rollback()
