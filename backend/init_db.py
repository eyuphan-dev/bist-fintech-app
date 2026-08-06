from datetime import datetime, timedelta
from sqlalchemy import text, inspect
from database import engine, Base, SessionLocal, IS_SQLITE
import models

# ---------------------------------------------------------------------------
# BİST Hisse Kataloğu + Katılım Endeksi (XKTUM) Uygunluk Bilgileri
#
# NOT: Aşağıdaki is_katilim_compliant / purification_rate / non_compliance_reason
# alanları bu simülasyon platformu için temsili örnek veridir; resmi BİST Katılım
# Tüm (XKTUM) endeksinin güncel, canlı bileşen listesiyle birebir örtüşmeyebilir.
# Gerçek yatırım kararları için resmi kaynaklara (BİST, KAP, danışman kuruluşlar)
# başvurulmalıdır — bu veriler yatırım tavsiyesi değildir.
# ---------------------------------------------------------------------------
INITIAL_STOCKS = [
    # --- Orijinal 26 Katılım Finans ağırlıklı küçük/orta ölçek hisse ---
    {"symbol": "ALBRK", "company_name": "Albaraka Türk Katılım Bankası A.Ş.", "sector": "Bankacılık", "is_katilim_compliant": True, "purification_rate": 0.10, "non_compliance_reason": None},
    {"symbol": "BAHKM", "company_name": "Bahadır Kimya Sanayi ve Ticaret A.Ş.", "sector": "Kimya", "is_katilim_compliant": True, "purification_rate": 1.20, "non_compliance_reason": None},
    {"symbol": "BEGYO", "company_name": "Batı Ege Gayrimenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 2.80, "non_compliance_reason": None},
    {"symbol": "BIMAS", "company_name": "BİM Birleşik Mağazalar A.Ş.", "sector": "Perakende", "is_katilim_compliant": True, "purification_rate": 1.40, "non_compliance_reason": None},
    {"symbol": "BINBN", "company_name": "Bin Ulaşım ve Akıllı Şehir Teknolojileri A.Ş.", "sector": "Teknoloji", "is_katilim_compliant": True, "purification_rate": 1.60, "non_compliance_reason": None},
    {"symbol": "BORSK", "company_name": "Bor Şeker A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 0.90, "non_compliance_reason": None},
    {"symbol": "BOSSA", "company_name": "Bossa Ticaret ve Sanayi İşletmeleri T.A.Ş.", "sector": "Tekstil", "is_katilim_compliant": True, "purification_rate": 2.30, "non_compliance_reason": None},
    {"symbol": "CELHA", "company_name": "Çelik Halat ve Tel Sanayii A.Ş.", "sector": "Demir-Çelik", "is_katilim_compliant": True, "purification_rate": 1.10, "non_compliance_reason": None},
    {"symbol": "COSMO", "company_name": "Cosmos Yatırım Holding A.Ş.", "sector": "Holding", "is_katilim_compliant": True, "purification_rate": 3.00, "non_compliance_reason": None},
    {"symbol": "DARDL", "company_name": "Dardanel Önentaş Gıda Sanayi A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 0.70, "non_compliance_reason": None},
    {"symbol": "DOFRB", "company_name": "Dof Robotik Sanayi A.Ş.", "sector": "Teknoloji", "is_katilim_compliant": True, "purification_rate": 1.90, "non_compliance_reason": None},
    {"symbol": "EBEBK", "company_name": "Ebebek Mağazacılık A.Ş.", "sector": "Perakende", "is_katilim_compliant": True, "purification_rate": 0.50, "non_compliance_reason": None},
    {"symbol": "EKSUN", "company_name": "Eksun Gıda Tarım Sanayi ve Ticaret A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 1.30, "non_compliance_reason": None},
    {"symbol": "ESCOM", "company_name": "Escort Teknoloji Yatırım A.Ş.", "sector": "Teknoloji", "is_katilim_compliant": True, "purification_rate": 2.10, "non_compliance_reason": None},
    {"symbol": "FZLGY", "company_name": "Fuzul Gayrimenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 2.60, "non_compliance_reason": None},
    {"symbol": "GUNDG", "company_name": "Gündoğdu Gıda Süt Ürünleri Sanayi ve Dış Ticaret A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 0.80, "non_compliance_reason": None},
    {"symbol": "IZFAS", "company_name": "İzmir Fırça Sanayi ve Ticaret A.Ş.", "sector": "Sanayi", "is_katilim_compliant": True, "purification_rate": 1.00, "non_compliance_reason": None},
    {"symbol": "IZINV", "company_name": "İz Yatırım Holding A.Ş.", "sector": "Holding", "is_katilim_compliant": True, "purification_rate": 2.40, "non_compliance_reason": None},
    {"symbol": "KRGYO", "company_name": "Körfez Gayrimenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 3.20, "non_compliance_reason": None},
    {"symbol": "KTLEV", "company_name": "Katılımevim Tasarruf Finansman A.Ş.", "sector": "Finansal Kiralama", "is_katilim_compliant": True, "purification_rate": 0.40, "non_compliance_reason": None},
    {"symbol": "KZBGY", "company_name": "Kızılbük Gayırmenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 2.90, "non_compliance_reason": None},
    {"symbol": "LXGYO", "company_name": "Luxera Gayrimenkul Yatırım Ortaklığı A.Ş.", "sector": "GYO", "is_katilim_compliant": True, "purification_rate": 2.20, "non_compliance_reason": None},
    {"symbol": "MCARD", "company_name": "Metropal Kurumsal Hizmetler A.Ş.", "sector": "Hizmetler", "is_katilim_compliant": True, "purification_rate": 1.50, "non_compliance_reason": None},
    {"symbol": "MPARK", "company_name": "MLP Sağlık Hizmetleri A.Ş. (Medical Park)", "sector": "Sağlık", "is_katilim_compliant": True, "purification_rate": 1.80, "non_compliance_reason": None},
    {"symbol": "PENGD", "company_name": "Penguen Gıda Sanayi A.Ş.", "sector": "Gıda", "is_katilim_compliant": True, "purification_rate": 0.60, "non_compliance_reason": None},
    {"symbol": "YUNSA", "company_name": "Yünsa Yünlü Sanayi ve Ticaret A.Ş.", "sector": "Tekstil", "is_katilim_compliant": True, "purification_rate": 1.70, "non_compliance_reason": None},

    # --- BIST 100 / BIST Tüm ağırlıklı büyük ölçek hisseler ---
    {"symbol": "THYAO", "company_name": "Türk Hava Yolları A.O.", "sector": "Ulaştırma", "is_katilim_compliant": True, "purification_rate": 2.10, "non_compliance_reason": None},
    {"symbol": "EREGL", "company_name": "Ereğli Demir ve Çelik Fabrikaları T.A.Ş.", "sector": "Demir-Çelik", "is_katilim_compliant": True, "purification_rate": 1.80, "non_compliance_reason": None},
    {"symbol": "TUPRS", "company_name": "Türkiye Petrol Rafinerileri A.Ş.", "sector": "Enerji", "is_katilim_compliant": True, "purification_rate": 3.40, "non_compliance_reason": None},
    {"symbol": "ASELS", "company_name": "Aselsan Elektronik Sanayi ve Ticaret A.Ş.", "sector": "Savunma", "is_katilim_compliant": True, "purification_rate": 1.20, "non_compliance_reason": None},
    {"symbol": "SISE", "company_name": "Türkiye Şişe ve Cam Fabrikaları A.Ş.", "sector": "Sanayi", "is_katilim_compliant": True, "purification_rate": 2.50, "non_compliance_reason": None},
    {"symbol": "KCHOL", "company_name": "Koç Holding A.Ş.", "sector": "Holding", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Grup bünyesindeki bankacılık/finans iştirakleri nedeniyle faiz geliri oranı Katılım Endeksi eşik değerini aşmaktadır."},
    {"symbol": "SAHOL", "company_name": "Hacı Ömer Sabancı Holding A.Ş.", "sector": "Holding", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Grup bünyesindeki bankacılık faaliyetleri (Akbank) nedeniyle faiz geliri oranı kriterleri karşılamamaktadır."},
    {"symbol": "GARAN", "company_name": "Türkiye Garanti Bankası A.Ş.", "sector": "Bankacılık", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Faiz bazlı mevduat bankacılığı faaliyeti yürütmektedir."},
    {"symbol": "AKBNK", "company_name": "Akbank T.A.Ş.", "sector": "Bankacılık", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Faiz bazlı mevduat bankacılığı faaliyeti yürütmektedir."},
    {"symbol": "FROTO", "company_name": "Ford Otomotiv Sanayi A.Ş.", "sector": "Otomotiv", "is_katilim_compliant": True, "purification_rate": 1.50, "non_compliance_reason": None},
    {"symbol": "TOASO", "company_name": "Tofaş Türk Otomobil Fabrikası A.Ş.", "sector": "Otomotiv", "is_katilim_compliant": True, "purification_rate": 1.70, "non_compliance_reason": None},
    {"symbol": "SASA", "company_name": "Sasa Polyester Sanayi A.Ş.", "sector": "Kimya", "is_katilim_compliant": True, "purification_rate": 0.90, "non_compliance_reason": None},
    {"symbol": "HEKTS", "company_name": "Hektaş Ticaret T.A.Ş.", "sector": "Kimya", "is_katilim_compliant": True, "purification_rate": 0.60, "non_compliance_reason": None},
    {"symbol": "ENKAI", "company_name": "Enka İnşaat ve Sanayi A.Ş.", "sector": "İnşaat", "is_katilim_compliant": True, "purification_rate": 4.20, "non_compliance_reason": None},
    {"symbol": "PETKM", "company_name": "Petkim Petrokimya Holding A.Ş.", "sector": "Kimya", "is_katilim_compliant": True, "purification_rate": 2.00, "non_compliance_reason": None},
    {"symbol": "OYAKC", "company_name": "Oyak Çimento A.Ş.", "sector": "İnşaat", "is_katilim_compliant": True, "purification_rate": 1.10, "non_compliance_reason": None},
    {"symbol": "MGROS", "company_name": "Migros Ticaret A.Ş.", "sector": "Perakende", "is_katilim_compliant": False, "purification_rate": 0.00,
     "non_compliance_reason": "Toplam faizli borç / piyasa değeri oranı Katılım Endeksi eşik değerini aşmaktadır."},
]

# Var olan tablolara sonradan eklenen kolonlar (SQLite ALTER TABLE ADD COLUMN destekler;
# create_all() zaten var olan tabloları güncellemediği için elle taşınır)
MIGRATIONS = {
    "users": {
        "baseline_value": "NUMERIC(15, 2) DEFAULT 100000.00",
    },
    "stocks": {
        "is_katilim_compliant": "INTEGER DEFAULT 0",
        "purification_rate": "NUMERIC(5, 2) DEFAULT 0.00",
        "non_compliance_reason": "TEXT",
        "sector": "TEXT",
        "previous_close": "NUMERIC(10, 2)",
    },
    "company_analysis": {
        "ev_ebitda": "NUMERIC(10, 2)",
        "roe": "NUMERIC(6, 2)",
        "gross_margin": "NUMERIC(6, 2)",
        "net_margin": "NUMERIC(6, 2)",
        "fx_exposure_text": "TEXT",
        "interest_sensitivity_text": "TEXT",
        "altman_z_score": "NUMERIC(6, 2)",
        "altman_zone": "TEXT",
        "debt_to_equity": "NUMERIC(8, 2)",
        "net_fx_position": "TEXT",
        "target_mean_price": "NUMERIC(10, 2)",
        "target_high_price": "NUMERIC(10, 2)",
        "target_low_price": "NUMERIC(10, 2)",
        "target_upside_pct": "NUMERIC(6, 2)",
        "number_of_analysts": "INTEGER",
        "recommendation_key": "TEXT",
        "analyst_buy_count": "INTEGER",
        "analyst_hold_count": "INTEGER",
        "analyst_sell_count": "INTEGER",
        "next_earnings_date": "DATE",
    },
    "user_bots": {
        "time_frame": "TEXT DEFAULT '1D'",
        "started_at": "TEXT",
        "ends_at": "TEXT",
        "baseline_value": "NUMERIC(15, 2) DEFAULT 100000.00",
        "performance_reset_at": "TEXT",
    },
    "portfolios": {
        "opened_at": "TEXT",
        "updated_at": "TEXT",
    },
    "bot_logs": {
        # İşlem anındaki bot zaman dilimi ('1D'/'1W'/'1M') — oturum bazlı
        # işlem günlüğü için sonradan eklendi, eski kayıtlarda NULL kalır.
        "time_frame": "VARCHAR(5)",
    },
}


def run_migrations():
    """
    Var olan tablolara eksik kolonları ekler. Tablo henüz yoksa create_all zaten doğru
    şemayla oluşturacaktır. SQLAlchemy inspector kullanıldığı için hem SQLite hem
    Postgres'te çalışır — Postgres'te (production) tablo daha önce create_all ile
    oluşturulmuş olsa bile, sonradan models.py'a eklenen yeni kolonlar create_all
    tarafından EKLENMEZ (create_all yalnızca eksik TABLOLARI oluşturur, var olan
    tablolara kolon eklemez); bu yüzden bu fonksiyon her ortamda çalıştırılmalıdır.
    """
    inspector = inspect(engine)
    with engine.connect() as conn:
        for table_name, column_defs in MIGRATIONS.items():
            if not inspector.has_table(table_name):
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
            for column_name, ddl in column_defs.items():
                if column_name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
                    print(f"'{table_name}' tablosuna '{column_name}' kolonu eklendi.")
        conn.commit()


def migrate_portfolios_table():
    """
    'portfolios' tablosunu is_bot_portfolio kolonu ve (user_id, stock_id, is_bot_portfolio)
    UNIQUE kısıtıyla yeniden oluşturur. SQLite'ta var olan bir UNIQUE kısıtını ALTER TABLE
    ile değiştirmek mümkün olmadığından, tablo yeniden inşa edilir (rebuild) ve veriler
    is_bot_portfolio=0 (kullanıcı manuel pozisyonu) varsayımıyla taşınır.
    """
    with engine.connect() as conn:
        existing_columns = {row[1] for row in conn.execute(text("PRAGMA table_info(portfolios)"))}
        if not existing_columns:
            return  # Tablo henüz yok; create_all doğru şemayla oluşturacak
        if "is_bot_portfolio" in existing_columns:
            return  # Zaten migrate edilmiş

        conn.execute(text("""
            CREATE TABLE portfolios_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stock_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                average_cost REAL NOT NULL,
                is_bot_portfolio INTEGER DEFAULT 0 NOT NULL,
                UNIQUE(user_id, stock_id, is_bot_portfolio),
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(stock_id) REFERENCES stocks(id)
            )
        """))
        conn.execute(text("""
            INSERT INTO portfolios_new (id, user_id, stock_id, quantity, average_cost, is_bot_portfolio)
            SELECT id, user_id, stock_id, quantity, average_cost, 0 FROM portfolios
        """))
        conn.execute(text("DROP TABLE portfolios"))
        conn.execute(text("ALTER TABLE portfolios_new RENAME TO portfolios"))
        conn.commit()
        print("'portfolios' tablosu is_bot_portfolio kolonu ile yeniden oluşturuldu.")


BOT_TIME_FRAME_DURATIONS = {
    "1D": timedelta(days=1),
    "1W": timedelta(weeks=1),
    "1M": timedelta(days=30),
}


def seed_user_bots(db):
    """Bot olmayan (is_bot=False) her kullanıcı için kişisel AI botu kaydı oluşturur."""
    users = db.query(models.User).filter_by(is_bot=False).all()
    created = 0
    now = datetime.utcnow()
    for user in users:
        exists = db.query(models.UserBot).filter_by(user_id=user.id).first()
        if not exists:
            db.add(models.UserBot(
                user_id=user.id,
                bot_name=f"{user.username} — Kişisel AI Bot",
                virtual_balance=100000.00,
                is_active=True,
                risk_profile="normal",
                time_frame="1D",
                started_at=now,
                ends_at=now + BOT_TIME_FRAME_DURATIONS["1D"],
            ))
            created += 1
    db.commit()
    if created:
        print(f"{created} kullanıcı için kişisel AI Bot kaydı oluşturuldu.")


def backfill_portfolio_timestamps(db):
    """Migration sonrası opened_at/updated_at boş kalan mevcut portfolios satırlarını doldurur."""
    now = datetime.utcnow()
    rows = db.query(models.Portfolio).filter(models.Portfolio.opened_at.is_(None)).all()
    for row in rows:
        row.opened_at = now
        row.updated_at = now
    if rows:
        db.commit()
        print(f"{len(rows)} portföy pozisyonu için tarih (opened_at/updated_at) bilgisi dolduruldu.")


def backfill_user_bot_durations(db):
    """Migration sonrası started_at/ends_at boş kalan mevcut user_bots satırlarını doldurur."""
    now = datetime.utcnow()
    bots = db.query(models.UserBot).filter(models.UserBot.started_at.is_(None)).all()
    for ub in bots:
        tf = ub.time_frame or "1D"
        ub.started_at = now
        ub.ends_at = now + BOT_TIME_FRAME_DURATIONS.get(tf, BOT_TIME_FRAME_DURATIONS["1D"])
    if bots:
        db.commit()
        print(f"{len(bots)} kişisel bot için süre (started_at/ends_at) bilgisi dolduruldu.")


def init_database():
    print("Veritabanı tabloları oluşturuluyor...")
    if IS_SQLITE:
        # UNIQUE kısıtı değişikliği gerektiren bu tam tablo yeniden inşası (rebuild)
        # yalnızca SQLite'a özgü bir sorunu (ALTER TABLE ile UNIQUE eklenememesi) çözer;
        # Postgres'teki portfolios tablosu zaten doğru şemayla oluşturulmuştur.
        migrate_portfolios_table()
    # run_migrations() hem SQLite hem Postgres'te çalışır: create_all() yalnızca EKSİK
    # TABLOLARI oluşturur, var olan bir tabloya sonradan eklenen kolonları eklemez —
    # bu yüzden production'daki (Postgres) var olan tablolar için de gereklidir.
    run_migrations()
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # 1. Seed / güncelle stocks (katılım endeksi bilgileri dahil)
        for stock_data in INITIAL_STOCKS:
            exists = db.query(models.Stock).filter_by(symbol=stock_data["symbol"]).first()
            if not exists:
                stock = models.Stock(
                    symbol=stock_data["symbol"],
                    company_name=stock_data["company_name"],
                    is_active=True,
                    sector=stock_data["sector"],
                    is_katilim_compliant=stock_data["is_katilim_compliant"],
                    purification_rate=stock_data["purification_rate"],
                    non_compliance_reason=stock_data["non_compliance_reason"],
                )
                db.add(stock)
                print(f"Hisse eklendi: {stock_data['symbol']}")
            else:
                exists.company_name = stock_data["company_name"]
                exists.is_active = True
                exists.sector = stock_data["sector"]
                exists.is_katilim_compliant = stock_data["is_katilim_compliant"]
                exists.purification_rate = stock_data["purification_rate"]
                exists.non_compliance_reason = stock_data["non_compliance_reason"]
                print(f"Hisse güncellendi: {stock_data['symbol']}")

        # 2. Seed AI Bot User (paylaşımlı demo bot — geriye dönük uyumluluk için korunur)
        bot_username = "yapay_zeka_trader"
        bot_exists = db.query(models.User).filter_by(username=bot_username).first()
        if not bot_exists:
            bot = models.User(
                username=bot_username,
                email="bot@borsasim.com",
                password_hash="pbkdf2:sha256:bot_dummy_password",
                virtual_balance=100000.00,
                is_bot=True
            )
            db.add(bot)
            print(f"Yapay Zeka Trader bot kullanıcısı oluşturuldu! (Başlangıç Bakiyesi: 100.000 TL)")

        db.commit()

        # 3. Seed TEFAS Katılım fonları (boş liste ile başlamasın diye)
        from tefas_client import seed_katilim_funds
        seed_katilim_funds(db)

        # 4. Her kullanıcı için kişisel AI Bot kaydı oluştur (yoksa)
        seed_user_bots(db)

        # 5. Migration sonrası eksik süre bilgilerini doldur
        backfill_user_bot_durations(db)

        # 6. Migration sonrası eksik portföy tarih bilgilerini doldur
        backfill_portfolio_timestamps(db)

        print("Veritabanı başarıyla ilklendirildi.")
    except Exception as e:
        print(f"Veritabanı ilklendirilirken hata oluştu: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
