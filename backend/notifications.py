"""
notifications.py
-----------------
Kişiye özel bildirim & alarm sistemi: kullanıcıların hisse bazlı fiyat/yüzde
limitleri, KAP bildirimleri ve AI sinyalleri için bıraktığı tercihleri (
StockNotificationPreference) kontrol edip tetiklenenler için Notification
kaydı oluşturur.

Tetikleme noktaları:
- Fiyat üstü/altı ve günlük % değişim: scheduler.py -> update_bist_prices_job()
  içinden, fiyat güncellemesi tamamlandıktan hemen sonra (her 5 dakikada bir,
  borsa açıkken) çağrılır.
- KAP bildirimi: kap_client.py -> fetch_kap_news() yeni bir KAP kaydı
  eklediğinde, o hisseyi izleyen kullanıcılar için çağrılır.
- AI sinyali: scheduler.py -> refresh_market_data_job() içinden günde bir kez
  (KAP/TEFAS tazelemesiyle aynı tetiklemede) çağrılır; kullanıcının kişisel bot
  ayarlarından bağımsız, referans "1 Günlük / Normal" strateji sinyali kullanılır.
"""

from datetime import datetime, date
from typing import Iterable, Optional
from sqlalchemy.orm import Session

import models


def _create_notification(db: Session, user_id: int, stock_id: Optional[int], notif_type: str, title: str, message: str) -> None:
    db.add(models.Notification(
        user_id=user_id,
        stock_id=stock_id,
        notif_type=notif_type,
        title=title,
        message=message,
    ))


def _get_latest_price_and_change(db: Session, stock_id: int):
    history = (
        db.query(models.StockPrice)
        .filter_by(stock_id=stock_id)
        .order_by(models.StockPrice.recorded_at.desc())
        .limit(2)
        .all()
    )
    if not history:
        return None, None
    current = float(history[0].price)
    if len(history) < 2 or float(history[1].price) <= 0:
        return current, None
    change_pct = ((current - float(history[1].price)) / float(history[1].price)) * 100
    return current, change_pct


def check_price_and_pct_triggers(db: Session) -> None:
    """Fiyat üstü/altı (bir kerelik) ve günlük % değişim (günde bir kerelik) alarmlarını kontrol eder."""
    preferences = (
        db.query(models.StockNotificationPreference)
        .filter(
            (models.StockNotificationPreference.price_above.isnot(None))
            | (models.StockNotificationPreference.price_below.isnot(None))
            | (models.StockNotificationPreference.pct_change_trigger.isnot(None))
        )
        .all()
    )
    if not preferences:
        return

    today = date.today()
    price_cache: dict[int, tuple] = {}

    for pref in preferences:
        if pref.stock_id not in price_cache:
            price_cache[pref.stock_id] = _get_latest_price_and_change(db, pref.stock_id)
        current_price, change_pct = price_cache[pref.stock_id]
        if current_price is None:
            continue

        stock = db.query(models.Stock).filter_by(id=pref.stock_id).first()
        if not stock:
            continue

        # Fiyat üstü alarmı — bir kerelik, tetiklendiğinde alan sıfırlanır
        if pref.price_above is not None and current_price >= float(pref.price_above):
            _create_notification(
                db, pref.user_id, pref.stock_id, "PRICE_ABOVE",
                f"{stock.symbol} hedef fiyatı aştı",
                f"{stock.symbol}, belirlediğiniz {float(pref.price_above):.2f} TL üst limitine ulaştı (güncel: {current_price:.2f} TL).",
            )
            pref.price_above = None

        # Fiyat altı alarmı — bir kerelik
        if pref.price_below is not None and current_price <= float(pref.price_below):
            _create_notification(
                db, pref.user_id, pref.stock_id, "PRICE_BELOW",
                f"{stock.symbol} alt limitin altına indi",
                f"{stock.symbol}, belirlediğiniz {float(pref.price_below):.2f} TL alt limitinin altına indi (güncel: {current_price:.2f} TL).",
            )
            pref.price_below = None

        # Günlük % değişim alarmı — aynı gün içinde tekrar tetiklenmez
        if (
            pref.pct_change_trigger is not None
            and change_pct is not None
            and abs(change_pct) >= float(pref.pct_change_trigger)
            and pref.last_pct_trigger_date != today
        ):
            direction = "yükseldi" if change_pct >= 0 else "düştü"
            _create_notification(
                db, pref.user_id, pref.stock_id, "PCT_CHANGE",
                f"{stock.symbol} %{float(pref.pct_change_trigger):.1f} üzeri hareket etti",
                f"{stock.symbol} bugün %{change_pct:.2f} {direction} (eşik: %{float(pref.pct_change_trigger):.1f}).",
            )
            pref.last_pct_trigger_date = today

    db.commit()


def check_kap_triggers(db: Session, new_kap_notifications: Iterable["models.KapNotification"]) -> None:
    """Yeni eklenen her KAP bildirimi için, o hisseyi izleyen (notify_kap=True) kullanıcılara bildirim oluşturur."""
    new_list = list(new_kap_notifications)
    if not new_list:
        return

    stock_ids = {n.stock_id for n in new_list if n.stock_id is not None}
    if not stock_ids:
        return

    watchers = (
        db.query(models.StockNotificationPreference)
        .filter(
            models.StockNotificationPreference.stock_id.in_(stock_ids),
            models.StockNotificationPreference.notify_kap.is_(True),
        )
        .all()
    )
    if not watchers:
        return

    watchers_by_stock: dict[int, list] = {}
    for w in watchers:
        watchers_by_stock.setdefault(w.stock_id, []).append(w)

    for notif in new_list:
        for watcher in watchers_by_stock.get(notif.stock_id, []):
            _create_notification(
                db, watcher.user_id, notif.stock_id, "KAP",
                f"{notif.symbol} için yeni KAP bildirimi",
                notif.title,
            )

    db.commit()


def check_ai_signal_triggers(db: Session) -> None:
    """
    notify_ai_signal=True olan izlemeler için referans "1 Günlük / Normal" strateji
    sinyalini (kullanıcının kişisel bot ayarlarından bağımsız, ortak bir gösterge
    olarak) hesaplar; AL/SAT üretilirse günde bir kez bildirim oluşturur.
    """
    from bot import get_strategy_config, get_risk_mode_config, _generate_timeframe_signal, DEFAULT_TIME_FRAME, DEFAULT_RISK_MODE

    preferences = (
        db.query(models.StockNotificationPreference)
        .filter(models.StockNotificationPreference.notify_ai_signal.is_(True))
        .all()
    )
    if not preferences:
        return

    config = get_strategy_config(DEFAULT_TIME_FRAME)
    risk_config = get_risk_mode_config(DEFAULT_RISK_MODE)
    today = date.today()
    signal_cache: dict[int, tuple] = {}

    for pref in preferences:
        if pref.last_ai_signal_date == today:
            continue

        if pref.stock_id not in signal_cache:
            price_records = (
                db.query(models.StockPrice)
                .filter_by(stock_id=pref.stock_id)
                .order_by(models.StockPrice.recorded_at.asc())
                .limit(500)
                .all()
            )
            if not price_records:
                signal_cache[pref.stock_id] = ("BEKLE", None, 0.0)
            else:
                signal_cache[pref.stock_id] = _generate_timeframe_signal(price_records, config, risk_config)

        action, _, confidence = signal_cache[pref.stock_id]
        if action == "BEKLE":
            continue

        stock = db.query(models.Stock).filter_by(id=pref.stock_id).first()
        if not stock:
            continue

        _create_notification(
            db, pref.user_id, pref.stock_id, "AI_SIGNAL",
            f"{stock.symbol} için AI sinyali: {action}",
            f"Referans strateji (1 Günlük / Normal), {stock.symbol} için %{confidence * 100:.0f} güvenle {action} sinyali üretti.",
        )
        pref.last_ai_signal_date = today

    db.commit()
