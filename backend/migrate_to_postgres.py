"""
migrate_to_postgres.py
-----------------------
Tek seferlik veri taşıma scripti: yerel bist_app.db (SQLite) içindeki gerçek
kullanıcı verilerini (users, user_bots, portfolios, bot_logs, pending_orders,
stock_comments, bot_performance_history) DATABASE_URL ile verilen Postgres'e
kopyalar. stocks/funds gibi statik katalog verileri init_database() tarafından
zaten taze olarak seed edildiği için buraya dahil edilmez; stock_prices geçmişi
de kopyalanmaz (scheduler zaten canlı olarak yeniden dolduracak).

Kullanım:
    DATABASE_URL=postgresql://... python migrate_to_postgres.py
"""
import os
import sqlite3
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from database import Base

TARGET_URL = os.environ.get("DATABASE_URL")
if not TARGET_URL:
    raise SystemExit("DATABASE_URL env var gerekli (hedef Postgres).")
if TARGET_URL.startswith("postgres://"):
    TARGET_URL = TARGET_URL.replace("postgres://", "postgresql://", 1)

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bist_app.db")

target_engine = create_engine(TARGET_URL, pool_pre_ping=True)
TargetSession = sessionmaker(bind=target_engine)

src_conn = sqlite3.connect(SQLITE_PATH)
src_conn.row_factory = sqlite3.Row


def rows(table, where=""):
    return src_conn.execute(f"SELECT * FROM {table} {where}").fetchall()


def parse_dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except (ValueError, TypeError):
            continue
    return None


def main():
    db = TargetSession()
    try:
        stock_id_map = {}
        for row in db.query(models.Stock).all():
            stock_id_map[row.symbol] = row.id

        src_stock_symbol = {r["id"]: r["symbol"] for r in rows("stocks")}

        user_id_map = {}
        migrated_users = 0
        for r in rows("users", "WHERE is_bot = 0"):
            existing = db.query(models.User).filter_by(username=r["username"]).first()
            if existing:
                user_id_map[r["id"]] = existing.id
                continue
            new_user = models.User(
                username=r["username"],
                email=r["email"],
                password_hash=r["password_hash"],
                virtual_balance=r["virtual_balance"],
                is_bot=False,
                created_at=parse_dt(r["created_at"]) or datetime.utcnow(),
                terms_accepted=bool(r["terms_accepted"]) if "terms_accepted" in r.keys() else True,
                terms_accepted_at=parse_dt(r["terms_accepted_at"]) if "terms_accepted_at" in r.keys() else None,
            )
            db.add(new_user)
            db.flush()
            user_id_map[r["id"]] = new_user.id
            migrated_users += 1
        db.commit()
        print(f"Kullanıcılar taşındı: {migrated_users} yeni (toplam eşleşen: {len(user_id_map)})")

        migrated_bots = 0
        for r in rows("user_bots"):
            old_user_id = r["user_id"]
            if old_user_id not in user_id_map:
                continue
            new_user_id = user_id_map[old_user_id]
            if db.query(models.UserBot).filter_by(user_id=new_user_id).first():
                continue
            db.add(models.UserBot(
                user_id=new_user_id,
                bot_name=r["bot_name"],
                virtual_balance=r["virtual_balance"],
                is_active=bool(r["is_active"]),
                risk_profile=r["risk_profile"],
                time_frame=r["time_frame"] if "time_frame" in r.keys() else "1D",
                started_at=parse_dt(r["started_at"]) if "started_at" in r.keys() else None,
                ends_at=parse_dt(r["ends_at"]) if "ends_at" in r.keys() else None,
                created_at=parse_dt(r["created_at"]) or datetime.utcnow(),
            ))
            migrated_bots += 1
        db.commit()
        print(f"Kişisel bot kayıtları taşındı: {migrated_bots}")

        migrated_portfolios = 0
        for r in rows("portfolios"):
            old_user_id = r["user_id"]
            if old_user_id not in user_id_map:
                continue
            symbol = src_stock_symbol.get(r["stock_id"])
            new_stock_id = stock_id_map.get(symbol)
            if not new_stock_id:
                continue
            new_user_id = user_id_map[old_user_id]
            is_bot_portfolio = bool(r["is_bot_portfolio"]) if "is_bot_portfolio" in r.keys() else False
            exists = db.query(models.Portfolio).filter_by(
                user_id=new_user_id, stock_id=new_stock_id, is_bot_portfolio=is_bot_portfolio
            ).first()
            if exists:
                continue
            db.add(models.Portfolio(
                user_id=new_user_id,
                stock_id=new_stock_id,
                quantity=r["quantity"],
                average_cost=r["average_cost"],
                is_bot_portfolio=is_bot_portfolio,
                opened_at=parse_dt(r["opened_at"]) if "opened_at" in r.keys() else None,
                updated_at=parse_dt(r["updated_at"]) if "updated_at" in r.keys() else None,
            ))
            migrated_portfolios += 1
        db.commit()
        print(f"Portföy pozisyonları taşındı: {migrated_portfolios}")

        migrated_bot_logs = 0
        for r in rows("bot_logs"):
            old_user_id = r["user_id"]
            if old_user_id not in user_id_map:
                continue
            symbol = src_stock_symbol.get(r["stock_id"])
            new_stock_id = stock_id_map.get(symbol)
            if not new_stock_id:
                continue
            db.add(models.BotLog(
                user_id=user_id_map[old_user_id],
                stock_id=new_stock_id,
                action_type=r["action_type"],
                price=r["price"],
                quantity=r["quantity"],
                reason_text=r["reason_text"],
                created_at=parse_dt(r["created_at"]) or datetime.utcnow(),
            ))
            migrated_bot_logs += 1
        db.commit()
        print(f"Bot işlem logları taşındı: {migrated_bot_logs}")

        migrated_perf = 0
        try:
            perf_rows = rows("bot_performance_history")
        except sqlite3.OperationalError:
            perf_rows = []
        for r in perf_rows:
            old_user_id = r["user_id"]
            if old_user_id not in user_id_map:
                continue
            db.add(models.BotPerformanceHistory(
                user_id=user_id_map[old_user_id],
                total_portfolio_value=r["total_portfolio_value"],
                recorded_date=r["recorded_date"],
            ))
            migrated_perf += 1
        db.commit()
        print(f"Bot performans geçmişi taşındı: {migrated_perf}")

        migrated_pending = 0
        try:
            pending_rows = rows("pending_orders")
        except sqlite3.OperationalError:
            pending_rows = []
        for r in pending_rows:
            old_user_id = r["user_id"]
            if old_user_id not in user_id_map:
                continue
            symbol = src_stock_symbol.get(r["stock_id"])
            new_stock_id = stock_id_map.get(symbol)
            if not new_stock_id:
                continue
            db.add(models.PendingOrder(
                user_id=user_id_map[old_user_id],
                stock_id=new_stock_id,
                order_type=r["order_type"],
                target_price=r["target_price"] if "target_price" in r.keys() else None,
                execution_time=parse_dt(r["execution_time"]) if "execution_time" in r.keys() else None,
                quantity=r["quantity"],
                status=r["status"],
                fail_reason=r["fail_reason"] if "fail_reason" in r.keys() else None,
                created_at=parse_dt(r["created_at"]) or datetime.utcnow(),
                executed_at=parse_dt(r["executed_at"]) if "executed_at" in r.keys() else None,
            ))
            migrated_pending += 1
        db.commit()
        print(f"Bekleyen emirler taşındı: {migrated_pending}")

        migrated_comments = 0
        for r in rows("stock_comments"):
            old_user_id = r["user_id"]
            if old_user_id not in user_id_map:
                continue
            symbol = src_stock_symbol.get(r["stock_id"])
            new_stock_id = stock_id_map.get(symbol)
            if not new_stock_id:
                continue
            db.add(models.StockComment(
                user_id=user_id_map[old_user_id],
                stock_id=new_stock_id,
                comment_text=r["comment_text"],
                sentiment_score=r["sentiment_score"],
                created_at=parse_dt(r["created_at"]) or datetime.utcnow(),
            ))
            migrated_comments += 1
        db.commit()
        print(f"Yorumlar taşındı: {migrated_comments}")

        print("\nTaşıma tamamlandı.")
    finally:
        db.close()
        src_conn.close()


if __name__ == "__main__":
    main()
