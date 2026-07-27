"""
scheduler.py
------------
APScheduler arka plan gorev yoneticisi.
"""

import sys
import io
import threading
# Windows konsolunda Turkce karakter sorununun onlenmesi
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
import models
from yfinance_client import fetch_current_price
from cache import set_latest_price
from datetime import datetime, timedelta
import pytz
from market_hours import is_market_open, TR_TZ
from kap_client import fetch_kap_news
from tefas_client import update_tefas_funds


# ---------------------------------------------------------------------------
# Başlangıç: DB'deki son fiyatlarla önbelleği doldur
# ---------------------------------------------------------------------------
def init_cache_from_db():
    """Uygulama başlarken veritabanındaki son fiyatları RAM önbelleğine yükler."""
    print("Önbellek (Cache) veritabanındaki son fiyatlarla dolduruluyor...")
    db = SessionLocal()
    try:
        stocks = db.query(models.Stock).filter_by(is_active=True).all()
        for stock in stocks:
            latest_record = (
                db.query(models.StockPrice)
                .filter_by(stock_id=stock.id)
                .order_by(models.StockPrice.recorded_at.desc())
                .first()
            )

            if latest_record:
                set_latest_price(
                    symbol=stock.symbol,
                    price=float(latest_record.price),
                    volume=latest_record.volume or 0,
                    recorded_at=latest_record.recorded_at,
                )
                print(f"  Önbelleğe alındı: {stock.symbol} → {latest_record.price} TL")
            else:
                res = fetch_current_price(stock.symbol)
                if res:
                    price, volume = res
                    now = datetime.utcnow()
                    set_latest_price(stock.symbol, price, volume, now)
                    db.add(
                        models.StockPrice(
                            stock_id=stock.id,
                            price=price,
                            volume=volume,
                            recorded_at=now,
                        )
                    )
                    print(f"  yfinance'dan yeni çekildi: {stock.symbol} → {price} TL")
        db.commit()
    except Exception as e:
        print(f"Önbellek ilklendirilirken hata: {e}")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# MODÜL 1: Fiyat Güncelleme + AI Bot Görevi
# ---------------------------------------------------------------------------
def update_bist_prices_job():
    """
    BİST hisse fiyatlarını günceller ve AI Trader botunu tetikler.

    ─── Borsa Saatleri Guard ───────────────────────────────────────────────
    Fonksiyon çağrılmadan önce is_market_open() ile durum kontrol edilir.
    • Borsa kapalıysa (hafta sonu, tatil veya saat dışı) işlem YAPILMAZ.
    • Sadece hafta içi 10:00–18:15 arasında gerçek iş yapılır.
    ────────────────────────────────────────────────────────────────────────

    Sunucu Cron (alternatif kullanım):
        */5 10-18 * * 1-5   → Hafta içi, saat 10–18 arası her 5 dakika
    """
    now_tr = datetime.now(TR_TZ)
    print(f"\n[Scheduler] Fiyat güncelleme görevi tetiklendi → {now_tr.strftime('%Y-%m-%d %H:%M:%S %Z')}")

    # ── Borsa Saatleri Guard ─────────────────────────────────────────────
    open_flag, reason = is_market_open()
    if not open_flag:
        print(f"[Scheduler] İşlem atlandı: {reason}")
        return
    # ─────────────────────────────────────────────────────────────────────

    db = SessionLocal()
    try:
        stocks = db.query(models.Stock).filter_by(is_active=True).all()
        now_utc = datetime.utcnow()

        updated = []
        for stock in stocks:
            res = fetch_current_price(stock.symbol)
            if res:
                price, volume = res
                db.add(
                    models.StockPrice(
                        stock_id=stock.id,
                        price=price,
                        volume=volume,
                        recorded_at=now_utc,
                    )
                )
                set_latest_price(stock.symbol, price, volume, now_utc)
                updated.append(f"{stock.symbol}({price})")

        db.commit()
        print(f"[Scheduler] Güncellenen hisseler: {', '.join(updated)}")

        # Bekleyen (LIMIT/SCHEDULED) kullanıcı emirleri — botla AYNI thread'de, bot'tan
        # ÖNCE işlenir (kullanıcının kendi bıraktığı emirler önceliklidir). Emirler
        # botun bakiye/portföyünden tamamen ayrı verilere dokunduğu için aralarında
        # herhangi bir çakışma söz konusu değildir.
        from orders import process_pending_orders
        process_pending_orders(db)

        # Çok kullanıcılı Quant AI Bot döngüsü (her kullanıcının kişisel botu + paylaşımlı demo bot)
        from bot import run_quant_bot
        run_quant_bot(db)

    except Exception as e:
        print(f"[Scheduler] Fiyat güncelleme hatası: {e}")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# MODÜL 1.5: KAP Bildirimleri + TEFAS Fon Fiyatları (Günlük Tazeleme)
# ---------------------------------------------------------------------------
def refresh_market_data_job():
    """
    KAP bildirimlerini ve TEFAS fon fiyatlarını arka planda tazeler.
    Bu iş bilerek API request-response döngüsünün DIŞINDA tutulur: KAP taraması
    tek başına ~40 hisse × dış API çağrısı gerektirdiği için dakikalarca
    sürebilir; kullanıcı isteğini bloklamamak için yalnızca scheduler üzerinden
    çalışır. /api/kap/news ve /api/funds uçları her zaman veritabanından
    (bu iş tarafından doldurulan) anlık okuma yapar.
    """
    db = SessionLocal()
    try:
        print("[Scheduler] KAP bildirimleri tazeleniyor...")
        try:
            fetch_kap_news(db)
        except Exception as e:
            print(f"[Scheduler] KAP tazeleme hatası: {e}")
            db.rollback()

        print("[Scheduler] TEFAS fon fiyatları tazeleniyor...")
        try:
            update_tefas_funds(db)
        except Exception as e:
            print(f"[Scheduler] TEFAS tazeleme hatası: {e}")
            db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# MODÜL 2: Log Temizleme Görevi (90 günden eski kayıtları sil)
# ---------------------------------------------------------------------------
def log_cleanup_job():
    """
    user_logs tablosundan 90 günden eski kayıtları siler.

    Tahmini Veri Yükü Analizi:
      - 15 kullanıcı × 20 log/gün × 90 gün = 27.000 satır
      - Satır başı ortalama ~200 byte → toplam ~5.4 MB
      - Bu görev çalıştıkça tablo ≤ 5 MB'da sabit kalır.

    Sunucu Cron önerisi: 0 3 * * 0  (Her Pazar 03:00)

    SQLite eşdeğeri:
        DELETE FROM user_logs WHERE created_at < datetime('now', '-90 days');

    PostgreSQL eşdeğeri:
        DELETE FROM user_logs WHERE created_at < NOW() - INTERVAL '90 days';
    """
    print("[Scheduler] Log temizleme görevi başlatıldı...")
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=90)
        deleted = (
            db.query(models.UserLog)
            .filter(models.UserLog.created_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"[Scheduler] Log temizleme tamamlandı. {deleted} eski kayıt silindi (kesme tarihi: {cutoff.date()}).")
    except Exception as e:
        print(f"[Scheduler] Log temizleme hatası: {e}")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scheduler Başlatma
# ---------------------------------------------------------------------------
def start_scheduler():
    """
    APScheduler'ı başlatır ve tüm cron görevlerini kaydeder.

    Görev Listesi:
      bist_updater      → Hafta içi 10:00–18:55, her 5 dakika
                          (market_guard içeride kontrol eder)
      market_data_sync  → Her gün 08:00 UTC (KAP bildirimleri + TEFAS fon fiyatları)
      log_cleaner       → Her Pazar 03:00 (UTC+0)
    """
    init_cache_from_db()

    # Uygulama ilk ayağa kalktığında KAP/TEFAS verisi boşsa kullanıcı bir sonraki
    # 08:00 tetiklenmesini beklemek zorunda kalmasın diye, arka planda (uygulama
    # başlangıcını bloklamadan) bir kerelik ilk tazeleme başlatılır.
    threading.Thread(target=refresh_market_data_job, daemon=True).start()

    scheduler = BackgroundScheduler()

    # ── Görev 1: BİST Fiyat Güncelleme ──────────────────────────────────
    # Hafta içi 10–18 saatleri arası her 5 dakika.
    # is_market_open() fonksiyonu içeride tam dakika bazlı kontrol yapar;
    # bu sayede 18:15'ten sonra tetiklense bile iş yapmaz.
    scheduler.add_job(
        update_bist_prices_job,
        "cron",
        day_of_week="mon-fri",
        hour="10-18",
        minute="*/5",
        timezone=TR_TZ,
        id="bist_updater",
        max_instances=1,         # Çakışan çalıştırmayı önler
        coalesce=True,           # Missed fires'ı birleştirir
    )

    # ── Görev 1.5: KAP + TEFAS Tazeleme ─────────────────────────────────
    # Her gün 08:00 UTC (Türkiye'de 11:00) — borsa açılışından sonra, gün içinde
    # bir kez. Ağır dış API taraması içerdiği için sık çalıştırılmaz.
    scheduler.add_job(
        refresh_market_data_job,
        "cron",
        hour=8,
        minute=0,
        id="market_data_sync",
        max_instances=1,
    )

    # ── Görev 2: Log Temizleme ───────────────────────────────────────────
    # Her Pazar sabahı 03:00 UTC (Türkiye'de 06:00)
    scheduler.add_job(
        log_cleanup_job,
        "cron",
        day_of_week="sun",
        hour=3,
        minute=0,
        id="log_cleaner",
        max_instances=1,
    )

    scheduler.start()
    print("APScheduler başlatıldı.")
    print("  • bist_updater     : Hafta içi 10:00–18:55, her 5 dakika")
    print("  • market_data_sync : Her gün 08:00 UTC (KAP bildirimleri + TEFAS fon fiyatları)")
    print("  • log_cleaner      : Her Pazar 03:00 UTC (90 günden eski logları siler)")
    return scheduler
