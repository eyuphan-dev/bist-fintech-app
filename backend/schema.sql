-- BIST Simülasyonu & AI Trader — SQLite Şeması (Midas Pro / Helal Finans Modülü Dahil)
-- Bu dosya, models.py (SQLAlchemy) içindeki tabloların referans SQL karşılığıdır.
-- Gerçek tablolar uygulama açılışında init_db.py / Base.metadata.create_all ile oluşturulur.

PRAGMA foreign_keys = ON;

-- 1. Kullanıcılar (Botlar dahil)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    virtual_balance REAL DEFAULT 100000.00,
    is_bot INTEGER DEFAULT 0,               -- 0: Kullanıcı, 1: Bot
    terms_accepted INTEGER DEFAULT 0 NOT NULL,
    terms_accepted_at TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 2. Hisseler ve Katılım Endeksi
CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    is_katilim_compliant INTEGER DEFAULT 0,  -- 0: Uygun Değil, 1: Uygun
    purification_rate REAL DEFAULT 0.00,     -- Arınma Oranı (%)
    non_compliance_reason TEXT
);

-- 3. Geçmiş Fiyat Verileri (Grafik & ML Eğitimi)
CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    price REAL NOT NULL,
    volume INTEGER,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stock_prices_time ON stock_prices(stock_id, recorded_at DESC);

-- 4. Kullanıcı / Bot Portföyleri
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    average_cost REAL NOT NULL,
    UNIQUE(user_id, stock_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(stock_id) REFERENCES stocks(id)
);

-- 5. Kullanıcı İşlem Logları (Hafif Yapı - Max 90 Günlük)
CREATE TABLE IF NOT EXISTS user_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_user_logs_user_id ON user_logs(user_id);
CREATE INDEX IF NOT EXISTS ix_user_logs_created_at ON user_logs(created_at);

-- 6. Bot İşlem Logları
CREATE TABLE IF NOT EXISTS bot_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    action_type TEXT NOT NULL, -- 'AL' / 'SAT'
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    reason_text TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(stock_id) REFERENCES stocks(id)
);

-- 7. Bot Günlük Bakiye Geçmişi (Karşılaştırma Grafiği İçin)
CREATE TABLE IF NOT EXISTS bot_performance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total_portfolio_value REAL NOT NULL,
    recorded_date TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_bot_performance_date ON bot_performance_history(user_id, recorded_date);

-- 8. Midas Pro Derin Analiz Tablosu
CREATE TABLE IF NOT EXISTS company_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER UNIQUE NOT NULL,
    piotroski_score INTEGER,        -- 0-9 arası
    pe_ratio REAL,                  -- F/K
    pb_ratio REAL,                  -- PD/DD
    ev_ebitda REAL,                 -- FD/FAVÖK
    sector_pe_avg REAL,             -- Sektör F/K
    fair_value REAL,                -- Makul Değer (Graham formülü)
    discount_rate REAL,             -- İskonto %
    roe REAL,                       -- Özkaynak Kârlılığı (%)
    gross_margin REAL,              -- Brüt Kâr Marjı (%)
    net_margin REAL,                -- Net Kâr Marjı (%)
    fx_exposure_text TEXT,          -- Döviz kuru riski açıklaması
    interest_sensitivity_text TEXT, -- Faiz hassasiyeti açıklaması
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

-- 9. İçeriden Öğrenenlerin Ticareti (Patron/Yönetim Alım-Satımı)
CREATE TABLE IF NOT EXISTS insider_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    title_person TEXT NOT NULL,     -- Unvan / kişi adı (örn. "Yönetim Kurulu Üyesi")
    trade_type TEXT NOT NULL,       -- 'ALIM' / 'SATIM'
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    trade_date TEXT NOT NULL,
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_insider_trades_stock ON insider_trades(stock_id, trade_date DESC);

-- 10. KAP Bildirimleri (Genel Haber Akışı)
CREATE TABLE IF NOT EXISTS kap_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    symbol TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    kap_url TEXT,
    publish_date TEXT NOT NULL,
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_kap_notifications_date ON kap_notifications(publish_date DESC);

-- 11. TEFAS Yatırım Fonları
CREATE TABLE IF NOT EXISTS funds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,      -- TEFAS fon kodu (örn. 'AFT')
    name TEXT NOT NULL,
    fund_type TEXT,                 -- 'Hisse Senedi', 'Katılım', 'Borçlanma Araçları' vb.
    risk_level INTEGER,             -- 1-7 arası TEFAS risk skalası
    is_katilim_compliant INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS fund_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id INTEGER NOT NULL,
    price REAL NOT NULL,
    daily_return REAL,
    monthly_return REAL,
    yearly_return REAL,
    recorded_date TEXT NOT NULL,
    FOREIGN KEY(fund_id) REFERENCES funds(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_fund_prices_date ON fund_prices(fund_id, recorded_date DESC);

-- 12. Halka Arzlar (IPO)
CREATE TABLE IF NOT EXISTS ipos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    symbol TEXT,
    offer_price REAL,
    demand_collection_dates TEXT,   -- "DD.MM.YYYY - DD.MM.YYYY"
    is_katilim_compliant INTEGER DEFAULT 0,
    lot_distribution_type TEXT      -- 'Eşit Dağıtım', 'Oransal Dağıtım' vb.
);

-- 13. Hisse Yorumları & Topluluk Duyarlılığı
CREATE TABLE IF NOT EXISTS stock_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    comment_text TEXT NOT NULL,
    sentiment_score REAL,           -- -1.0 (negatif) ile +1.0 (pozitif) arası
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stock_comments_stock ON stock_comments(stock_id, created_at DESC);
