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
from constants import EXTREME_CHANGE_GUARD_PCT


def _create_notification(
    db: Session,
    user_id: int,
    stock_id: Optional[int],
    notif_type: str,
    title: str,
    message: str,
    outbox: Optional[list] = None,
    url: str = "/",
) -> None:
    """
    Uygulama içi bildirim kaydını oluşturur ve istenirse push kutusuna ekler.

    Push BURADA GÖNDERİLMEZ. Bu fonksiyon henüz commit edilmemiş bir işlemin
    içinde çalışır; buradan gönderilen bir push, işlem geri alınırsa var
    olmayan bir bildirimi duyurmuş olurdu. Ayrıca push bir HTTP çağrısıdır ve
    işlemi ağ süresi kadar açık tutmak istemeyiz. Bunun yerine yük `outbox`a
    yazılır, çağıran commit'ten sonra push.send_outbox ile boşaltır.
    """
    db.add(models.Notification(
        user_id=user_id,
        stock_id=stock_id,
        notif_type=notif_type,
        title=title,
        message=message,
    ))
    if outbox is not None:
        import push
        outbox.append({
            "user_id": user_id,
            "payload": push.build_payload(title, message, url=url, tag=f"{notif_type}-{stock_id}"),
        })


def _flush(db: Session, outbox: list) -> None:
    """
    Push kutusunu boşaltır. Commit'ten SONRA çağrılır.

    Push gönderimi bir yan etkidir; başarısız olması alarmın kendisini
    geçersiz kılmaz (bildirim zaten veritabanına yazıldı ve kullanıcı
    uygulama içinde görecek). Bu yüzden tüm hatalar burada yutulur.
    """
    if not outbox:
        return
    try:
        import push
        sent = push.send_outbox(db, outbox)
        if sent:
            print(f"[Push] {sent} cihaza gönderildi ({len(outbox)} bildirim).")
    except Exception as e:
        print(f"[Push] kutu boşaltılamadı: {e}")


def _get_latest_price_and_change(db: Session, stock_id: int):
    """
    Güncel fiyat ve GÜNLÜK % değişim (önceki iş gününün kapanışına göre) döner.

    Önceki sürüm son iki StockPrice kaydı (5 dakikalık tik) arasındaki farkı
    "günlük değişim" olarak kullanıyordu — kullanıcı "%5 günlük değişimde uyar"
    dese bile gün boyunca kademeli büyüyen bir hareket hiç yakalanmıyor, tek bir
    5 dakikalık sert spike ise günlük eşiğin çok altında kalsa bile yanlışlıkla
    tetikleyebiliyordu (bkz. main.py:get_stocks'taki aynı düzeltme).
    """
    latest = (
        db.query(models.StockPrice)
        .filter_by(stock_id=stock_id)
        .order_by(models.StockPrice.recorded_at.desc())
        .first()
    )
    if not latest:
        return None, None
    current = float(latest.price)

    # Öncelik: Yahoo'nun resmi previousClose referansı (bkz. main.py:_bulk_price_and_change
    # docstring'i) — yoksa kendi stock_prices_daily türetmemize düşülür.
    stock = db.query(models.Stock).filter_by(id=stock_id).first()
    prev_close: Optional[float] = float(stock.previous_close) if stock and stock.previous_close is not None else None

    if prev_close is None:
        prev_close_row = (
            db.query(models.StockPriceDaily)
            .filter(models.StockPriceDaily.stock_id == stock_id, models.StockPriceDaily.trade_date < date.today())
            .order_by(models.StockPriceDaily.trade_date.desc())
            .first()
        )
        prev_close = float(prev_close_row.close) if prev_close_row and float(prev_close_row.close) > 0 else None

    if prev_close is None or prev_close <= 0:
        return current, None
    change_pct = ((current - prev_close) / prev_close) * 100
    # Kurumsal işlem (bölünme/bedelsiz) sonrası yanlış alarm tetiklememek için
    # aynı koruma (bkz. main.py:EXTREME_CHANGE_GUARD_PCT).
    if abs(change_pct) > EXTREME_CHANGE_GUARD_PCT:
        return current, None
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
    outbox: list = []

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
                outbox=outbox, url=f"/hisse/{stock.symbol}",
            )
            pref.price_above = None

        # Fiyat altı alarmı — bir kerelik
        if pref.price_below is not None and current_price <= float(pref.price_below):
            _create_notification(
                db, pref.user_id, pref.stock_id, "PRICE_BELOW",
                f"{stock.symbol} alt limitin altına indi",
                f"{stock.symbol}, belirlediğiniz {float(pref.price_below):.2f} TL alt limitinin altına indi (güncel: {current_price:.2f} TL).",
                outbox=outbox, url=f"/hisse/{stock.symbol}",
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
                outbox=outbox, url=f"/hisse/{stock.symbol}",
            )
            pref.last_pct_trigger_date = today

    db.commit()
    _flush(db, outbox)


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

    outbox: list = []
    watchers_by_stock: dict[int, list] = {}
    for w in watchers:
        watchers_by_stock.setdefault(w.stock_id, []).append(w)

    for notif in new_list:
        for watcher in watchers_by_stock.get(notif.stock_id, []):
            _create_notification(
                db, watcher.user_id, notif.stock_id, "KAP",
                f"{notif.symbol} için yeni KAP bildirimi",
                notif.title,
                outbox=outbox, url=f"/hisse/{notif.symbol}",
            )

    db.commit()
    _flush(db, outbox)


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
    outbox: list = []

    for pref in preferences:
        if pref.last_ai_signal_date == today:
            continue

        if pref.stock_id not in signal_cache:
            # DESC + limit, sonra kronolojik sıraya çevir (bkz. bot.py'deki aynı düzeltme) —
            # asc + limit birikmiş geçmişte en eski 500 kaydı döndürüp sinyali donduruyordu.
            price_records = (
                db.query(models.StockPrice)
                .filter_by(stock_id=pref.stock_id)
                .order_by(models.StockPrice.recorded_at.desc())
                .limit(500)
                .all()
            )
            price_records.reverse()
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
            outbox=outbox, url=f"/hisse/{stock.symbol}",
        )
        pref.last_ai_signal_date = today

    db.commit()
    _flush(db, outbox)
