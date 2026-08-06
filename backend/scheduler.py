"""
scheduler.py
------------
APScheduler arka plan gorev yoneticisi.
"""

import sys
import io
import threading
import time
# Windows konsolunda Turkce karakter sorununun onlenmesi
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
import models
from yfinance_client import fetch_current_price, fetch_stock_news
from cache import set_latest_price
from datetime import datetime, timedelta, date
import pytz
from market_hours import is_market_open, TR_TZ
from kap_client import fetch_kap_news
from tefas_client import update_tefas_funds
from analysis_engine import refresh_earnings_calendar
from daily_history import refresh_daily_history


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
                    price, volume, previous_close = res
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
                    if previous_close is not None:
                        stock.previous_close = previous_close
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
        for i, stock in enumerate(stocks):
            # Hisseler arası kısa bekleme: Yahoo'ya art arda patlama (burst) istek
            # göndermeyi önler — sunucu tek egress IP kullandığından, hızlı ardışık
            # istekler Yahoo tarafında geçici "Too Many Requests" bloğuna yol açabiliyor.
            if i > 0:
                time.sleep(0.4)
            res = fetch_current_price(stock.symbol)
            if res:
                price, volume, previous_close = res
                db.add(
                    models.StockPrice(
                        stock_id=stock.id,
                        price=price,
                        volume=volume,
                        recorded_at=now_utc,
                    )
                )
                if previous_close is not None:
                    stock.previous_close = previous_close
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

        # Kullanıcı bazlı fiyat üstü/altı ve günlük % değişim alarmları
        from notifications import check_price_and_pct_triggers
        check_price_and_pct_triggers(db)

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

        print("[Scheduler] Bilanço takvimi (yaklaşan bilanço tarihleri) tazeleniyor...")
        try:
            updated = refresh_earnings_calendar(db)
            print(f"[Scheduler] Bilanço takvimi tazelendi: {updated} hisse güncellendi.")
        except Exception as e:
            print(f"[Scheduler] Bilanço takvimi tazeleme hatası: {e}")
            db.rollback()

        # 1H/1A/1Y/5Y grafik seçenekleri için günlük OHLCV geçmişi (bkz. daily_history.py).
        # İlk çalıştırmada hisse başına tam 5 yıl çekildiği için bu adım dakikalar
        # sürebilir — bilerek burada, kullanıcı isteğinin dışında tutuluyor.
        print("[Scheduler] Günlük fiyat geçmişi (1H/1A/1Y/5Y grafikleri) tazeleniyor...")
        try:
            updated = refresh_daily_history(db)
            print(f"[Scheduler] Günlük geçmiş tazelendi: {updated} hisse güncellendi.")
        except Exception as e:
            print(f"[Scheduler] Günlük geçmiş tazeleme hatası: {e}")
            db.rollback()

        print("[Scheduler] AI sinyal alarmları kontrol ediliyor...")
        try:
            from notifications import check_ai_signal_triggers
            check_ai_signal_triggers(db)
        except Exception as e:
            print(f"[Scheduler] AI sinyal alarmı kontrol hatası: {e}")
            db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# MODÜL 1.6: Hisse Haberleri (Yahoo Finance) — 24 Saatlik Döngü
# ---------------------------------------------------------------------------
def refresh_stock_news_job():
    """
    Her aktif hisse için Yahoo Finance'dan son haberleri çeker ve stock_news
    tablosuna yazar. 24 saatlik döngü: bu görev günde bir kez çalışır, her
    hissenin BİR ÖNCEKİ günden kalan haber kayıtlarını siler ve günün yeni
    haberleriyle değiştirir — böylece "Haberler" sekmesi kalıcı, günlük olarak
    loglanmış bir veri setinden okur (yalnızca kısa ömürlü RAM önbelleğinden değil).
    """
    db = SessionLocal()
    try:
        print("[Scheduler] Hisse haberleri (Yahoo Finance) günlük olarak tazeleniyor...")
        stocks = db.query(models.Stock).filter_by(is_active=True).all()
        total_saved = 0
        for i, stock in enumerate(stocks):
            if i > 0:
                time.sleep(0.4)
            try:
                items = fetch_stock_news(stock.symbol, limit=8)
            except Exception as e:
                print(f"[Scheduler] {stock.symbol} haberleri çekilemedi: {e}")
                continue

            # Önceki günün kayıtlarını sil (24 saatlik döngü: eskiler silinip yenilerle değiştirilir)
            db.query(models.StockNews).filter_by(stock_id=stock.id).delete(synchronize_session=False)

            for item in items:
                if not item.get("title"):
                    continue
                db.add(models.StockNews(
                    stock_id=stock.id,
                    symbol=stock.symbol,
                    title=item["title"][:500],
                    summary=item.get("summary"),
                    source=item.get("source"),
                    url=item.get("url"),
                    thumbnail=item.get("thumbnail"),
                    published_at=item.get("published_at"),
                ))
                total_saved += 1
            db.commit()
        print(f"[Scheduler] Hisse haberleri tazelendi: {len(stocks)} hisse tarandı, {total_saved} haber kaydedildi.")
    except Exception as e:
        print(f"[Scheduler] Hisse haberleri tazeleme hatası: {e}")
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Kullanıcı Portföy Değeri Günlük Anlık Görüntüsü
# ---------------------------------------------------------------------------
def snapshot_user_portfolios_job():
    """
    Her kullanıcının (bot değil, kendi manuel portföyünün) o günkü toplam değerini
    user_performance_history tablosuna yazar — böylece kullanıcı zaman içindeki
    performansını grafikte görebilir.

    Aynı gün içinde tekrar çalışırsa mevcut kaydın üzerine yazar (gün başına tek
    satır); bu sayede seans içinde birden fazla tetiklense de tablo şişmez.
    Bot portföyleri bu görevin dışındadır, onları bot.py kendi döngüsünde yazar.
    """
    print("[Scheduler] Kullanıcı portföy değerleri kaydediliyor...")
    db = SessionLocal()
    try:
        today = date.today()
        users = db.query(models.User).filter_by(is_bot=False).all()

        # Fiyatları her kullanıcı için tekrar sorgulamamak adına tek seferde okunur.
        latest_prices = {}
        for stock_id, price in (
            db.query(models.StockPrice.stock_id, models.StockPrice.price)
            .order_by(models.StockPrice.stock_id, models.StockPrice.recorded_at.desc())
            .all()
        ):
            latest_prices.setdefault(stock_id, float(price))

        saved = 0
        for user in users:
            positions = db.query(models.Portfolio).filter_by(
                user_id=user.id, is_bot_portfolio=False
            ).all()
            stock_value = sum(
                float(p.quantity) * latest_prices.get(p.stock_id, 0.0) for p in positions
            )
            total_value = float(user.virtual_balance) + stock_value

            existing = db.query(models.UserPerformanceHistory).filter_by(
                user_id=user.id, recorded_date=today
            ).first()
            if existing:
                existing.total_portfolio_value = total_value
            else:
                db.add(models.UserPerformanceHistory(
                    user_id=user.id,
                    total_portfolio_value=total_value,
                    recorded_date=today,
                ))
            saved += 1

        db.commit()
        print(f"[Scheduler] {saved} kullanıcının portföy değeri kaydedildi.")
    except Exception as e:
        print(f"[Scheduler] Portföy anlık görüntüsü alınamadı: {e}")
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
    threading.Thread(target=refresh_stock_news_job, daemon=True).start()

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

    # ── Görev 1.6: Hisse Haberleri (Yahoo Finance) — 24 Saatlik Döngü ───
    # Her gün 07:30 UTC (Türkiye'de 10:30) — önceki günün haberleri silinip
    # günün yeni haberleriyle değiştirilir.
    scheduler.add_job(
        refresh_stock_news_job,
        "cron",
        hour=7,
        minute=30,
        id="stock_news_sync",
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

    # ── Görev 3: Kullanıcı Portföy Değeri Anlık Görüntüsü ────────────────
    # Hafta içi her gün seans kapanışından sonra (18:30 TR = 15:30 UTC)
    scheduler.add_job(
        snapshot_user_portfolios_job,
        "cron",
        day_of_week="mon-fri",
        hour=15,
        minute=30,
        id="user_portfolio_snapshot",
        max_instances=1,
    )

    scheduler.start()
    print("APScheduler başlatıldı.")
    print("  • bist_updater     : Hafta içi 10:00–18:55, her 5 dakika")
    print("  • market_data_sync : Her gün 08:00 UTC (KAP bildirimleri + TEFAS fon fiyatları)")
    print("  • stock_news_sync  : Her gün 07:30 UTC (Hisse haberleri, 24 saatlik döngü)")
    print("  • log_cleaner      : Her Pazar 03:00 UTC (90 günden eski logları siler)")
    return scheduler
