"""
scheduler.py
------------
APScheduler arka plan gorev yoneticisi.
"""

import sys
import threading
import time
# Windows konsolunda Turkce karakter sorununun onlenmesi
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal
import models
from yfinance_client import fetch_current_price, fetch_current_prices_batch, fetch_stock_news
from cache import set_latest_price
from datetime import datetime, timedelta, date
from market_hours import is_market_open, TR_TZ
from kap_client import fetch_kap_news
from tefas_client import update_tefas_funds
from analysis_engine import refresh_earnings_calendar
from daily_history import refresh_daily_history, refresh_index_history, refresh_market_quotes


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
                    price, volume = res["price"], res["volume"]
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
                    if res.get("previous_close") is not None:
                        stock.previous_close = res["previous_close"]
                    if res.get("open") is not None:
                        stock.open_price = res["open"]
                    if res.get("high") is not None:
                        stock.day_high = res["high"]
                    if res.get("low") is not None:
                        stock.day_low = res["low"]
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

        # TOPLU ÇEKİM: hisse başına ayrı istek atmak yerine yf.download ile
        # 40'lık partiler halinde tek istekte çekilir. Katalog 43'ten 165 hisseye
        # çıkarıldığında tek tek çekim ~3.5 dakikaya uzuyordu; tetikleme aralığı
        # 5 dakika olduğu için Yahoo bir gün yavaşladığında turlar üst üste
        # biner, max_instances=1 yüzünden tetiklemeler sessizce atlanır ve
        # fiyatlar bayatlardı. Ölçüm: 89 sembol tek tek ~107 sn, toplu 18 sn.
        symbols = [s.symbol for s in stocks]
        batch = fetch_current_prices_batch(symbols)
        print(f"[Scheduler] Toplu çekim: {len(batch)}/{len(symbols)} hisse.")

        updated = []
        eksik = 0
        for i, stock in enumerate(stocks):
            res = batch.get(stock.symbol)
            if res is None:
                # Partide gelmeyen tek tük sembol için tekil çekime düşülür.
                # Bunlar azınlıkta kaldığı sürece toplam süre etkilenmez.
                eksik += 1
                if eksik > 1:
                    time.sleep(0.4)
                res = fetch_current_price(stock.symbol)
            if res:
                price, volume = res["price"], res["volume"]
                db.add(
                    models.StockPrice(
                        stock_id=stock.id,
                        price=price,
                        volume=volume,
                        recorded_at=now_utc,
                    )
                )
                if res.get("previous_close") is not None:
                    stock.previous_close = res["previous_close"]
                # Seansın resmi açılış/yüksek/düşüğü — kendi tiklerimizden türetmek yerine
                # Yahoo'nun gün içi barlarından gelir (bkz. yfinance_client.fetch_current_price).
                if res.get("open") is not None:
                    stock.open_price = res["open"]
                if res.get("high") is not None:
                    stock.day_high = res["high"]
                if res.get("low") is not None:
                    stock.day_low = res["low"]
                set_latest_price(stock.symbol, price, volume, now_utc)
                updated.append(f"{stock.symbol}({price})")

        db.commit()
        if eksik:
            print(f"[Scheduler] {eksik} hisse toplu partide gelmedi, tek tek çekildi.")
        print(f"[Scheduler] {len(updated)} hisse güncellendi.")

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

        # SİNYAL ÖNBELLEĞİNİ ISIT: /api/signals 30 dakikalık bir önbellek
        # kullanıyor ve önbellek soğukken tarama 165 hissede saniyeler sürüyor.
        # Bunu kullanıcının isteği sırasında ödemek yerine burada, zaten
        # çalışan işin içinde ödüyoruz; böylece sayfayı açan hiç kimse soğuk
        # önbelleğe denk gelmiyor. Hata olursa görmezden gelinir — bu bir
        # iyileştirmedir, fiyat güncellemesini düşürmemeli.
        try:
            from signals import scan_signals
            scan_signals(db, use_cache=False)
        except Exception as e:
            print(f"[Scheduler] Sinyal önbelleği ısıtılamadı: {e}")

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

        # BIST 100 endeks geçmişi — portföy/endeks kıyaslaması (benchmark) için.
        print("[Scheduler] BIST 100 endeks geçmişi tazeleniyor...")
        try:
            refresh_index_history(db)
        except Exception as e:
            print(f"[Scheduler] Endeks geçmişi tazeleme hatası: {e}")
            db.rollback()

        # Döviz kurları ve altın — hisse yanında izlenen referans seriler.
        print("[Scheduler] Döviz ve altın fiyatları tazeleniyor...")
        try:
            refresh_market_quotes(db)
        except Exception as e:
            print(f"[Scheduler] Döviz/altın tazeleme hatası: {e}")
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
def refresh_deep_analysis_job(batch_size: int = 40):
    """
    Derin bilanço analizini (F/K, PD/DD, ROE, Piotroski, Altman Z, hedef fiyat...)
    arka planda tazeler.

    NEDEN EKLENDİ: calculate_deep_analysis hiçbir zamanlanmış işe bağlı değildi;
    yalnızca kullanıcı bir hissenin analiz sekmesinde "Tazele" dediğinde
    hesaplanıyordu. Sonuç: 43 aktif hissenin yalnızca 9'unda F/K verisi vardı,
    karşılaştırma sayfası ve tarayıcı çoğu hissede "—" gösteriyordu.

    Her çalıştırmada TÜM hisseler değil, en "bayat" `batch_size` kadarı işlenir:
    hisse başına birkaç yfinance çağrısı (info + financials + balance_sheet +
    recommendations) gerektiği için 43 hissenin tamamı tek seferde dakikalarca
    sürer ve Yahoo tarafında hız limitine takılma riski doğurur. Öncelik sırası:
    hiç analizi olmayanlar → en eski güncellenenler. Günlük çalışınca birkaç
    günde tüm katalog tazelenmiş olur ve sürekli döner.
    """
    from analysis_engine import calculate_deep_analysis, AnalysisFetchError

    db = SessionLocal()
    try:
        # Hiç kaydı olmayan veya en eski güncellenen hisseler önce gelsin.
        # NULLS FIRST: analizi hiç hesaplanmamış olanlar en yüksek öncelikli.
        rows = (
            db.query(models.Stock)
            .outerjoin(models.CompanyAnalysis, models.CompanyAnalysis.stock_id == models.Stock.id)
            .filter(models.Stock.is_active == True)
            .order_by(models.CompanyAnalysis.updated_at.asc().nullsfirst())
            .limit(batch_size)
            .all()
        )

        print(f"[Scheduler] Derin analiz tazeleniyor ({len(rows)} hisse)...")
        ok = 0
        for i, stock in enumerate(rows):
            if i > 0:
                time.sleep(1.0)  # Yahoo'ya art arda patlama istek göndermemek için
            try:
                if calculate_deep_analysis(db, stock.symbol):
                    ok += 1
            except AnalysisFetchError as e:
                print(f"[Scheduler]   {stock.symbol}: veri çekilemedi ({e})")
                db.rollback()
            except Exception as e:
                # Tek bir hissenin hatası tüm partiyi düşürmemeli.
                print(f"[Scheduler]   {stock.symbol}: analiz hatası ({e})")
                db.rollback()

        print(f"[Scheduler] Derin analiz tazelendi: {ok}/{len(rows)} hisse.")

        # Çeyreklik finansal tablolar — aynı gece işinde, ayrı parti hâlinde.
        try:
            from financials import refresh_financials_batch
            # Katalog 165 hisseye çıktığı için parti de büyütüldü; 8'de
            # kalsaydı tam tur 21 gün sürerdi. Finansal tablolar çeyreklik
            # yayımlandığı için ~8 günlük tur fazlasıyla yeterli.
            refresh_financials_batch(db, batch_size=20)

            # Katılım ön taraması: bilanço partisi tazelendikten HEMEN SONRA
            # çalışır ki oranlar en güncel bilanço üzerinden hesaplansın.
            # Tarama tamamen veritabanı içidir (dış çağrı yok), bu yüzden her
            # gün tüm katalog için çalıştırılabilir.
            try:
                from katilim import tum_katalogu_tara
                tum_katalogu_tara(db)
            except Exception as e:
                print(f"[Scheduler] Katılım taraması hatası: {e}")
                db.rollback()
        except Exception as e:
            print(f"[Scheduler] Finansal tablo tazeleme hatası: {e}")
            db.rollback()
    except Exception as e:
        print(f"[Scheduler] Derin analiz işi hatası: {e}")
        db.rollback()
    finally:
        db.close()


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

    prune_intraday_ticks()


# Gün içi tikler kaç gün saklanır. Grafiğin "1G" aralığı ve bot/alarm sinyalleri
# yalnızca son birkaç yüz tike bakar; uzun vadeli geçmiş zaten stock_prices_daily
# tablosunda günlük barlar hâlinde duruyor.
TICK_RETENTION_DAYS = 45


def prune_intraday_ticks():
    """
    stock_prices tablosundan eski gün içi tikleri siler.

    NEDEN GEREKLİ: bu tablo süresiz büyüyor ve katalog 43'ten 165 hisseye
    çıkınca büyüme hızı dörde katlandı — 165 hisse × 12 kayıt/saat × ~8,5 saat
    ≈ günde 17 bin satır, yani üç ayda ~1,2 milyon satır. Fiyat listesi sorgusu
    hisse başına en yeni tiki bulmak için bölümün tamamını okumak zorunda
    olduğundan, bu büyüme doğrudan /api/stocks gecikmesine yansıyordu.

    45 gün, bot ve alarm mantığının baktığı 500 tiklik pencereyi fazlasıyla
    kapsar (tek başına bir işlem günü bile hisse başına ~100 tik üretir).
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=TICK_RETENTION_DAYS)
        deleted = (
            db.query(models.StockPrice)
            .filter(models.StockPrice.recorded_at < cutoff)
            .delete(synchronize_session=False)
        )
        db.commit()
        if deleted:
            print(f"[Scheduler] Gün içi tik temizliği: {deleted} satır silindi (< {cutoff.date()}).")
        else:
            print("[Scheduler] Gün içi tik temizliği: silinecek kayıt yok.")
    except Exception as e:
        print(f"[Scheduler] Tik temizleme hatası: {e}")
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

    # ── Görev 4: Derin Bilanço Analizi Tazeleme ──────────────────────────
    # Her gün 02:00 UTC (Türkiye'de 05:00) — borsa kapalıyken, hisse başına
    # birkaç yfinance çağrısı gerektiren ağır iş. Her çalıştırmada en bayat 40
    # hisse işlenir; 165 hisselik katalog ~4 günde bir tam tur tazelenir.
    # (Parti 15'te bırakılsaydı katalog büyümesiyle tur 11 güne çıkardı.)
    scheduler.add_job(
        refresh_deep_analysis_job,
        "cron",
        hour=2,
        minute=0,
        id="deep_analysis_sync",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    print("APScheduler başlatıldı.")
    print("  • deep_analysis_sync: Her gün 02:00 UTC (en bayat 40 hissenin bilanço analizi)")
    print("  • bist_updater     : Hafta içi 10:00–18:55, her 5 dakika")
    print("  • market_data_sync : Her gün 08:00 UTC (KAP bildirimleri + TEFAS fon fiyatları)")
    print("  • stock_news_sync  : Her gün 07:30 UTC (Hisse haberleri, 24 saatlik döngü)")
    print("  • log_cleaner      : Her Pazar 03:00 UTC (90 günden eski logları siler)")
    return scheduler
