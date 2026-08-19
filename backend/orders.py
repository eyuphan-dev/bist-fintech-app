"""
orders.py
---------
Bekleyen (LIMIT_BUY / LIMIT_SELL / SCHEDULED_BUY) emirlerin borsa seans saatlerinde
otomatik kontrolü ve gerçekleştirilmesi.

Tasarım notları:
- Bu modül scheduler.py'deki update_bist_prices_job() içinden, fiyat güncellemesi
  tamamlandıktan hemen sonra AYNI arka plan thread'inde çağrılır (ayrı bir cron job
  DEĞİLDİR). Böylece AI bot (run_quant_bot) ile aynı tetiklemede sırayla çalışır —
  iki ayrı scheduler job'ının aynı anda farklı thread'lerde koşup birbirine
  çarpması ihtimali yapısal olarak ortadan kalkar; Render gibi tek instance'lı,
  kısıtlı kaynaklı bir ortamda ekstra thread/kaynak yükü de oluşturmaz.
- Emirler kullanıcının KENDİ manuel bakiyesi/portföyü üzerinde çalışır
  (User.virtual_balance, Portfolio.is_bot_portfolio=False) — AI bot'un bakiyesi
  (UserBot.virtual_balance) ve pozisyonları (is_bot_portfolio=True) tamamen ayrı
  satırlarda tutulduğu için botla veri çakışması mümkün değildir.
- Kullanıcının manuel /api/trade isteğiyle aynı ana denk gelme ihtimaline karşı
  (FastAPI istek thread'i vs. scheduler thread'i) her emir kendi BEGIN IMMEDIATE
  transaction'ı içinde, execute_trade ile aynı atomiklik deseniyle işlenir.
"""

from datetime import datetime
from sqlalchemy.orm import Session

import models
from database import begin_write_transaction
from market_hours import is_market_open
from transactions import record_transaction


def _get_latest_price(db: Session, stock_id: int) -> float:
    latest = (
        db.query(models.StockPrice)
        .filter_by(stock_id=stock_id)
        .order_by(models.StockPrice.recorded_at.desc())
        .first()
    )
    return float(latest.price) if latest else 0.0


def _should_execute(order: "models.PendingOrder", current_price: float, now_utc: datetime) -> bool:
    if order.order_type == "LIMIT_BUY":
        return current_price > 0 and current_price <= float(order.target_price)
    if order.order_type == "LIMIT_SELL":
        return current_price > 0 and current_price >= float(order.target_price)
    # STOP_LOSS_SELL, LIMIT_SELL'in TERSİ yönde tetiklenir: fiyat hedefe DÜŞTÜĞÜNDE
    # satar. LIMIT_SELL kâr almak için (fiyat yükselince), STOP_LOSS_SELL zararı
    # kesmek için (fiyat düşünce) kullanılır — koşulu karıştırmak emrin tam ters
    # anda çalışması demek olurdu.
    if order.order_type == "STOP_LOSS_SELL":
        return current_price > 0 and current_price <= float(order.target_price)
    if order.order_type == "SCHEDULED_BUY":
        return order.execution_time is not None and order.execution_time <= now_utc
    return False


def _fail_order(db: Session, order: "models.PendingOrder", reason: str) -> None:
    order.status = "FAILED"
    order.fail_reason = reason
    order.executed_at = datetime.utcnow()
    db.commit()
    print(f"[Orders] Emir #{order.id} başarısız: {reason}")


def _execute_single_order(db: Session, order_id: int) -> None:
    """Tek bir emri kendi atomik transaction'ında işler; bir emrin başarısız olması diğerlerini etkilemez."""
    db.rollback()
    begin_write_transaction(db)
    try:
        order = db.query(models.PendingOrder).filter_by(id=order_id, status="PENDING").first()
        if not order:
            db.rollback()
            return

        current_price = _get_latest_price(db, order.stock_id)
        if not current_price:
            _fail_order(db, order, "Hisse fiyatı bulunamadı.")
            return

        user = db.query(models.User).filter_by(id=order.user_id).first()
        if not user:
            _fail_order(db, order, "Kullanıcı bulunamadı.")
            return

        quantity = float(order.quantity)
        portfolio_entry = db.query(models.Portfolio).filter_by(
            user_id=user.id, stock_id=order.stock_id, is_bot_portfolio=False
        ).first()

        if order.order_type in ("LIMIT_BUY", "SCHEDULED_BUY"):
            total_cost = quantity * current_price
            if float(user.virtual_balance) < total_cost:
                _fail_order(db, order, f"Yetersiz bakiye (gerekli: {total_cost:.2f} TL).")
                return

            user.virtual_balance = float(user.virtual_balance) - total_cost
            if portfolio_entry:
                old_qty = float(portfolio_entry.quantity)
                old_cost = float(portfolio_entry.average_cost)
                new_qty = old_qty + quantity
                portfolio_entry.average_cost = ((old_qty * old_cost) + total_cost) / new_qty
                portfolio_entry.quantity = new_qty
            else:
                db.add(models.Portfolio(
                    user_id=user.id, stock_id=order.stock_id,
                    quantity=quantity, average_cost=current_price, is_bot_portfolio=False,
                ))

            record_transaction(
                db, user_id=user.id, stock_id=order.stock_id, action_type="AL",
                quantity=quantity, price=current_price, source="LIMIT_ORDER",
            )

        else:  # LIMIT_SELL / STOP_LOSS_SELL — ikisi de satis, yalnizca tetikleme kosullari farkli
            if not portfolio_entry or float(portfolio_entry.quantity) < quantity:
                _fail_order(db, order, "Yetersiz hisse miktarı.")
                return

            revenue = quantity * current_price
            user.virtual_balance = float(user.virtual_balance) + revenue
            # Ortalama maliyet satıştan ÖNCE okunur; pozisyon kapanırsa satır silinir.
            avg_cost_before_sale = float(portfolio_entry.average_cost)
            remaining = float(portfolio_entry.quantity) - quantity
            if remaining <= 0:
                db.delete(portfolio_entry)
            else:
                portfolio_entry.quantity = remaining

            record_transaction(
                db, user_id=user.id, stock_id=order.stock_id, action_type="SAT",
                quantity=quantity, price=current_price,
                average_cost=avg_cost_before_sale, source="LIMIT_ORDER",
            )

        order.status = "EXECUTED"
        order.executed_at = datetime.utcnow()

        # OCO (one-cancels-other): bir satış emri gerçekleştiğinde, aynı hisse için
        # bekleyen DİĞER satış emirleri artık karşılanamayacak kadar lot bırakmış
        # olabilir. Kalan pozisyondan büyük olanlar iptal edilir; aksi halde ileride
        # "Yetersiz hisse miktarı" ile FAILED olup kullanıcıya hata gibi görünürlerdi.
        # Tipik kullanım: aynı pozisyona kâr-al + zarar-kes koymak; biri çalışınca
        # diğeri kendiliğinden iptal olur.
        if order.order_type in ("LIMIT_SELL", "STOP_LOSS_SELL"):
            remaining_qty = float(portfolio_entry.quantity) if (portfolio_entry and remaining > 0) else 0.0
            siblings = db.query(models.PendingOrder).filter(
                models.PendingOrder.user_id == user.id,
                models.PendingOrder.stock_id == order.stock_id,
                models.PendingOrder.status == "PENDING",
                models.PendingOrder.id != order.id,
                models.PendingOrder.order_type.in_(("LIMIT_SELL", "STOP_LOSS_SELL")),
            ).all()
            for sib in siblings:
                if float(sib.quantity) > remaining_qty:
                    sib.status = "CANCELLED"
                    sib.fail_reason = "Pozisyon başka bir satış emriyle kapandığı için iptal edildi."
                    print(f"[Orders]   Kardeş emir #{sib.id} iptal edildi (OCO).")

        db.commit()
        print(f"[Orders] Emir #{order.id} gerçekleşti: {order.order_type} {quantity} adet @ {current_price} TL (user_id={user.id})")
    except Exception as e:
        db.rollback()
        print(f"[Orders] Emir #{order_id} işlenirken hata: {e}")


def process_pending_orders(db: Session) -> None:
    """
    Borsa açıksa bekleyen tüm emirleri kontrol eder, şartı sağlayanları gerçekleştirir.
    scheduler.py -> update_bist_prices_job() içinden çağrılır.
    """
    open_flag, _ = is_market_open()
    if not open_flag:
        return

    now_utc = datetime.utcnow()
    db.rollback()  # önceki adımdan (fiyat güncelleme commit'i) kalan açık transaction varsa temizle

    pending_orders = db.query(models.PendingOrder).filter_by(status="PENDING").all()
    if not pending_orders:
        return

    to_execute = [
        order.id for order in pending_orders
        if _should_execute(order, _get_latest_price(db, order.stock_id), now_utc)
    ]

    if to_execute:
        print(f"[Orders] {len(to_execute)} bekleyen emir gerçekleştirme şartını sağladı, işleniyor...")
    for order_id in to_execute:
        _execute_single_order(db, order_id)
