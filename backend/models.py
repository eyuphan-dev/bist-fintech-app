from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    virtual_balance = Column(Numeric(15, 2), default=100000.00)
    # Getiri (%) hesabının referans sermayesi. Kullanıcı bakiyesini manuel
    # değiştirdiğinde (/api/user/balance) bu alan da aynı miktarda kaydırılır
    # (bkz. UserBot.baseline_value ile aynı mantık) — aksi halde kullanıcı
    # bakiyesini örn. 1.000.000 TL'ye ayarlayıp hiç işlem yapmadan liderlik
    # tablosunda sahte %900 kâr gösterebilirdi.
    baseline_value = Column(Numeric(15, 2), default=100000.00)
    is_bot = Column(Boolean, default=False)
    # KVKK & Sorumluluk reddi onayı (kayıt sırasında zorunlu)
    terms_accepted = Column(Boolean, default=False, nullable=False)
    terms_accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    portfolios = relationship("Portfolio", back_populates="user", cascade="all, delete-orphan")
    bot_logs = relationship("BotLog", back_populates="user", cascade="all, delete-orphan")
    performance_history = relationship("BotPerformanceHistory", back_populates="user", cascade="all, delete-orphan")
    user_logs = relationship("UserLog", back_populates="user", cascade="all, delete-orphan")
    personal_bot = relationship("UserBot", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    company_name = Column(String(150), nullable=False)
    is_active = Column(Boolean, default=True)
    sector = Column(String(50), nullable=True, index=True)

    # Katılım Endeksi (Helal Finans) Uygunluk Bilgileri
    is_katilim_compliant = Column(Boolean, default=False)
    purification_rate = Column(Numeric(5, 2), default=0.00)  # Arınma Oranı (%)
    non_compliance_reason = Column(String, nullable=True)

    # Yahoo Finance'ın resmi "önceki kapanış" referansı (fast_info.previousClose),
    # scheduler her fiyat güncellemesinde tazeler. Günlük % değişim hesabında
    # kendi stock_prices_daily türetmemizden ÖNCE bu kullanılır — BİST'in tedbir/
    # taban-tavan referans fiyatı kurallarını Yahoo bizden daha doğru yansıtıyor
    # (bkz. GUNDG örneği: kendi hesabımız -%18.9 derken gerçek taban -%9.96'ydı).
    previous_close = Column(Numeric(10, 2), nullable=True)

    # Relationships
    prices = relationship("StockPrice", back_populates="stock", cascade="all, delete-orphan")
    portfolios = relationship("Portfolio", back_populates="stock")
    bot_logs = relationship("BotLog", back_populates="stock")
    analysis = relationship("CompanyAnalysis", back_populates="stock", uselist=False, cascade="all, delete-orphan")


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    volume = Column(Integer, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    stock = relationship("Stock", back_populates="prices")


class StockPriceDaily(Base):
    """
    Uzun vadeli grafik seçenekleri (1H/1A/1Y/5Y) için GÜNLÜK kapanış barları.
    stock_prices tablosundaki 5 dakikalık gün-içi tiklerden bilerek ayrı
    tutulur — aksi halde farklı aralıklardaki kayıtlar karışıp teknik
    gösterge/AI bot hesaplamalarındaki "son N kayıt = son N tik" varsayımını
    bozar. Hisse başına günde en fazla 1 kayıt olur (trade_date unique).
    """
    __tablename__ = "stock_prices_daily"
    __table_args__ = (UniqueConstraint("stock_id", "trade_date", name="uq_stock_daily_date"),)

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    open = Column(Numeric(12, 2), nullable=True)
    high = Column(Numeric(12, 2), nullable=True)
    low = Column(Numeric(12, 2), nullable=True)
    close = Column(Numeric(12, 2), nullable=False)
    volume = Column(Integer, nullable=True)

    stock = relationship("Stock")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    quantity = Column(Numeric(12, 4), nullable=False)
    average_cost = Column(Numeric(10, 2), nullable=False)
    # 0/False: kullanıcının kendi manuel pozisyonu, 1/True: kullanıcının kişisel AI botunun pozisyonu.
    # Aynı user_id + stock_id çifti hem manuel hem bot pozisyonu olarak ayrı ayrı var olabilsin diye
    # UNIQUE kısıtı bu kolonu da kapsar.
    is_bot_portfolio = Column(Boolean, default=False, nullable=False)
    # opened_at: pozisyon ilk açıldığındaki (ilk alım) zaman damgası, sonraki ek alımlarda DEĞİŞMEZ.
    # updated_at: pozisyona en son dokunulduğu (herhangi bir alım/satım) an, her işlemde güncellenir.
    opened_at = Column(DateTime, default=datetime.utcnow, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "stock_id", "is_bot_portfolio", name="uq_user_stock_bot"),
    )

    # Relationships
    user = relationship("User", back_populates="portfolios")
    stock = relationship("Stock", back_populates="portfolios")


class BotLog(Base):
    __tablename__ = "bot_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    action_type = Column(String(10), nullable=False)  # 'AL' or 'SAT'
    price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Numeric(12, 4), nullable=False)
    reason_text = Column(String, nullable=True)
    # İşlem anında botun çalıştığı zaman dilimi ('1D'/'1W'/'1M') — bot loglarını
    # strateji bazında filtreleyip gruplayabilmek için (eski kayıtlarda NULL olabilir).
    time_frame = Column(String(5), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="bot_logs")
    stock = relationship("Stock", back_populates="bot_logs")


class BotSession(Base):
    """
    Kişisel botun her başlatılıp durdurulduğu/süresi dolduğu dönemi (oturum) temsil eder.
    UI'da "bot 10 kere başlatılmış" listesi buradan gelir; her oturumun kapsadığı zaman
    aralığında (started_at - ended_at) yapılan işlemler BotLog.created_at üzerinden eşlenir
    (ayrı bir FK yerine zaman aralığı kullanılır ki eski BotLog kayıtları da geriye dönük
    oturumlarla eşleşebilsin).
    """
    __tablename__ = "bot_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    time_frame = Column(String(5), nullable=False)
    risk_mode = Column(String(20), nullable=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)  # NULL = hâlâ aktif oturum
    end_reason = Column(String, nullable=True)

    user = relationship("User")


class UserPerformanceHistory(Base):
    """
    Kullanıcının KENDİ portföyünün (bot değil) gün sonu toplam değeri.
    BotPerformanceHistory ile aynı yapıda, ama kullanıcının manuel işlemlerinden
    oluşan portföyünü izler; ikisi grafikte karşılaştırılabilsin diye ayrı tutulur.
    """
    __tablename__ = "user_performance_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    total_portfolio_value = Column(Numeric(15, 2), nullable=False)
    recorded_date = Column(Date, nullable=False, index=True)

    __table_args__ = (UniqueConstraint("user_id", "recorded_date", name="uq_user_perf_user_date"),)


class BotPerformanceHistory(Base):
    __tablename__ = "bot_performance_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    total_portfolio_value = Column(Numeric(15, 2), nullable=False)
    recorded_date = Column(Date, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="performance_history")


# ---------------------------------------------------------------------------
# MODÜL 2: Kullanıcı İşlem Logları (UserLog)
# ---------------------------------------------------------------------------
class UserLog(Base):
    """
    Kullanıcı hareket logları tablosu.

    Amaç   : 10-15 kullanıcı için giriş, işlem, takip ekleme gibi olayları kaydeder.
    Temizlik: 90 günden eski kayıtlar otomatik olarak silinir (bkz. log_cleanup_job).

    Tahmini Veri Yükü (3 ay / 15 kullanıcı):
      - Günlük ortalama 20 log/kullanıcı × 15 kullanıcı = 300 satır/gün
      - 90 gün × 300 satır = 27.000 satır
      - Satır başı ~200 byte (JSON details dahil) → ~5.4 MB max
      - Otomatik temizlik ile tüm zamanlar için üst limit ≤ 5 MB'da kalır.

    SQL Şeması (SQLite & PostgreSQL uyumlu):
      CREATE TABLE user_logs (
          id         INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          action     VARCHAR(50) NOT NULL,
          details    TEXT,
          ip_address VARCHAR(45),
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      );
      CREATE INDEX ix_user_logs_user_id    ON user_logs(user_id);
      CREATE INDEX ix_user_logs_created_at ON user_logs(created_at);

    PostgreSQL Otomatik Temizlik (Cron):
      -- Her gece 03:00'da çalıştır:
      -- 0 3 * * * psql -U app -d bist_db -c "DELETE FROM user_logs WHERE created_at < NOW() - INTERVAL '90 days';"
    """
    __tablename__ = "user_logs"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action     = Column(String(50), nullable=False)   # LOGIN, TRADE_BUY, TRADE_SELL, WATCHLIST_ADD, etc.
    details    = Column(Text, nullable=True)          # JSON string with extra context
    ip_address = Column(String(45), nullable=True)    # IPv4 or IPv6
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="user_logs")


# ---------------------------------------------------------------------------
# MODÜL 3: Derin Bilanço Analizi (CompanyAnalysis)
# ---------------------------------------------------------------------------
class CompanyAnalysis(Base):
    """Piotroski skoru, F/K, PD/DD ve makul değer analizi (Derin Bilanço Analizi)."""
    __tablename__ = "company_analysis"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), unique=True, nullable=False)
    piotroski_score = Column(Integer, nullable=True)   # 0-9 arası
    pe_ratio = Column(Numeric(10, 2), nullable=True)   # F/K
    pb_ratio = Column(Numeric(10, 2), nullable=True)   # PD/DD
    ev_ebitda = Column(Numeric(10, 2), nullable=True)  # FD/FAVÖK
    sector_pe_avg = Column(Numeric(10, 2), nullable=True)  # Sektör F/K
    fair_value = Column(Numeric(10, 2), nullable=True)     # Makul Değer (Graham)
    discount_rate = Column(Numeric(6, 2), nullable=True)   # İskonto %
    roe = Column(Numeric(6, 2), nullable=True)              # Özkaynak Kârlılığı %
    gross_margin = Column(Numeric(6, 2), nullable=True)     # Brüt Kâr Marjı %
    net_margin = Column(Numeric(6, 2), nullable=True)       # Net Kâr Marjı %
    fx_exposure_text = Column(String, nullable=True)        # Döviz kuru riski açıklaması
    interest_sensitivity_text = Column(String, nullable=True)  # Faiz hassasiyeti açıklaması
    altman_z_score = Column(Numeric(6, 2), nullable=True)      # Altman Z-Skoru (iflas riski)
    altman_zone = Column(String(20), nullable=True)            # 'SAFE' | 'GREY' | 'DISTRESS'
    debt_to_equity = Column(Numeric(8, 2), nullable=True)      # Borç/Özkaynak oranı
    net_fx_position = Column(String(20), nullable=True)        # 'POZITIF' | 'NEGATIF' | 'NOTR' (heuristik)

    # Aracı Kurum Hedef Fiyatları & Konsensüs (yfinance analist verisi)
    target_mean_price = Column(Numeric(10, 2), nullable=True)
    target_high_price = Column(Numeric(10, 2), nullable=True)
    target_low_price = Column(Numeric(10, 2), nullable=True)
    target_upside_pct = Column(Numeric(6, 2), nullable=True)   # (hedef ort. - güncel fiyat) / güncel fiyat
    number_of_analysts = Column(Integer, nullable=True)
    recommendation_key = Column(String(20), nullable=True)     # 'strong_buy' | 'buy' | 'hold' | 'sell' | 'strong_sell'
    analyst_buy_count = Column(Integer, nullable=True)
    analyst_hold_count = Column(Integer, nullable=True)
    analyst_sell_count = Column(Integer, nullable=True)

    # Bilanço Takvimi: bir sonraki çeyreklik bilanço açıklama tarihi (yfinance tahmini)
    next_earnings_date = Column(Date, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stock = relationship("Stock", back_populates="analysis")


# ---------------------------------------------------------------------------
# MODÜL 3.5: Yabancı Takas Oranı Anlık Görüntüleri (Foreign Holding Trend)
# ---------------------------------------------------------------------------
class ForeignHoldingSnapshot(Base):
    """
    Her derin analiz tazelemesinde yfinance'tan alınan kurumsal/yabancı sahiplik
    oranının (heldPercentInstitutions, en yakın halka açık proxy) günlük anlık
    görüntüsü. 30/90 günlük değişim trendi bu tablodan hesaplanır — BİST için
    gerçek Takasbank yabancı oranı verisi halka açık/ücretsiz bir API üzerinden
    sağlanmadığından, bu alan en iyi çaba (best-effort) proxy'dir.
    """
    __tablename__ = "foreign_holding_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    held_pct = Column(Numeric(6, 2), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    stock = relationship("Stock")


# ---------------------------------------------------------------------------
# MODÜL 4: İçeriden Öğrenenlerin Ticareti (Insider Trades)
# ---------------------------------------------------------------------------
class InsiderTrade(Base):
    __tablename__ = "insider_trades"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(10), nullable=False)
    title_person = Column(String(150), nullable=False)
    trade_type = Column(String(10), nullable=False)  # 'ALIM' / 'SATIM'
    quantity = Column(Numeric(15, 4), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    trade_date = Column(DateTime, nullable=False, index=True)

    stock = relationship("Stock")


# ---------------------------------------------------------------------------
# MODÜL 5: KAP Bildirimleri (Genel Haber Akışı)
# ---------------------------------------------------------------------------
class KapNotification(Base):
    __tablename__ = "kap_notifications"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=True)
    symbol = Column(String(10), nullable=False)
    title = Column(String(300), nullable=False)
    summary = Column(Text, nullable=True)
    kap_url = Column(String(500), nullable=True)
    publish_date = Column(DateTime, nullable=False, index=True)

    stock = relationship("Stock")


# ---------------------------------------------------------------------------
# MODÜL 6: TEFAS Yatırım Fonları
# ---------------------------------------------------------------------------
class StockNews(Base):
    """
    Hisse bazlı haberler (Yahoo Finance/yfinance) — 24 saatlik döngüyle günlük olarak
    tazelenir: scheduler her gün bir kez çalışıp bir hissenin eski haber kayıtlarını
    silip günün yeni haberleriyle değiştirir (bkz. scheduler.py refresh_stock_news_job).
    """
    __tablename__ = "stock_news"

    id = Column(Integer, primary_key=True, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(10), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    source = Column(String(120), nullable=True)
    url = Column(String(500), nullable=True)
    thumbnail = Column(String(500), nullable=True)
    published_at = Column(String(50), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow, index=True)

    stock = relationship("Stock")


class Fund(Base):
    __tablename__ = "funds"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    fund_type = Column(String(50), nullable=True)
    risk_level = Column(Integer, nullable=True)  # 1-7 (TEFAS risk skalası)
    is_katilim_compliant = Column(Boolean, default=False)

    prices = relationship("FundPrice", back_populates="fund", cascade="all, delete-orphan")


class FundPrice(Base):
    __tablename__ = "fund_prices"

    id = Column(Integer, primary_key=True, index=True)
    fund_id = Column(Integer, ForeignKey("funds.id", ondelete="CASCADE"), nullable=False)
    price = Column(Numeric(12, 6), nullable=False)
    daily_return = Column(Numeric(6, 2), nullable=True)
    monthly_return = Column(Numeric(6, 2), nullable=True)
    yearly_return = Column(Numeric(6, 2), nullable=True)
    recorded_date = Column(Date, nullable=False, index=True)

    fund = relationship("Fund", back_populates="prices")


# ---------------------------------------------------------------------------
# MODÜL 7: Halka Arzlar (IPO)
# ---------------------------------------------------------------------------
class Ipo(Base):
    __tablename__ = "ipos"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String(200), nullable=False)
    symbol = Column(String(10), nullable=True)
    offer_price = Column(Numeric(10, 2), nullable=True)
    demand_collection_dates = Column(String(60), nullable=True)
    is_katilim_compliant = Column(Boolean, default=False)
    lot_distribution_type = Column(String(50), nullable=True)


# ---------------------------------------------------------------------------
# MODÜL 8: Hisse Yorumları & Topluluk Duyarlılığı
# ---------------------------------------------------------------------------
class StockComment(Base):
    __tablename__ = "stock_comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    comment_text = Column(String(500), nullable=False)
    sentiment_score = Column(Numeric(4, 2), nullable=True)  # -1.00 .. +1.00
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")
    stock = relationship("Stock")


# ---------------------------------------------------------------------------
# MODÜL 9: Çok Kullanıcılı Kişisel Yapay Zeka Botu (UserBot)
# ---------------------------------------------------------------------------
class UserBot(Base):
    """
    Her kullanıcının kendine ait, kendi sanal bakiyesiyle çalışan kişisel AI botu.
    Bot pozisyonları portfolios tablosunda aynı user_id ile is_bot_portfolio=1
    olarak tutulur; işlem günlükleri bot_logs tablosunda yine aynı user_id ile
    (legacy paylaşımlı demo bot 'yapay_zeka_trader' kullanıcısından farklı bir id
    olduğu için) çakışma yaşanmaz.
    """
    __tablename__ = "user_bots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    bot_name = Column(String(50), nullable=False, default="Kişisel AI Bot")
    virtual_balance = Column(Numeric(15, 2), default=100000.00)
    is_active = Column(Boolean, default=True)
    risk_profile = Column(String(20), default="normal")  # 'slow' | 'normal' | 'aggressive'
    # Süre & Zaman Dilimi Bazlı Strateji Motoru
    time_frame = Column(String(4), default="1D")  # '1D' Gün İçi/Scalp, '1W' Swing, '1M' Trend/Pozisyon
    started_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Getiri (%) hesabının referans sermayesi. Bakiye manuel değiştirildiğinde (para
    # ekleme/çıkarma) aynı miktarda ayarlanır ki yatırılan/çekilen nakit "kâr" gibi
    # görünmesin — yalnızca piyasa hareketinden gelen kâr/zarar % olarak yansır.
    baseline_value = Column(Numeric(15, 2), default=100000.00)
    # Bot pasif hale getirildiğinde (performans sıfırlama onayıyla) bu an'a güncellenir;
    # istatistikler (işlem sayısı, win rate) yalnızca bu tarihten sonraki BotLog kayıtlarını sayar.
    performance_reset_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="personal_bot")


# ---------------------------------------------------------------------------
# MODÜL 10: Bekleyen Emirler (Limit / Zamanlı Alım-Satım)
# ---------------------------------------------------------------------------
class PendingOrder(Base):
    """
    Kullanıcının manuel portföyü için bıraktığı LIMIT (fiyat şartlı) veya SCHEDULED
    (zaman şartlı) emirler. Yalnızca kullanıcının KENDİ manuel bakiyesi/portföyü
    (is_bot_portfolio=False) üzerinde çalışır — AI bot'un bakiyesi/pozisyonları
    (UserBot, is_bot_portfolio=True) tamamen ayrı olduğu için botla veri çakışması
    yapısal olarak mümkün değildir.
    """
    __tablename__ = "pending_orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False)
    order_type = Column(String(20), nullable=False)  # 'LIMIT_BUY' | 'LIMIT_SELL' | 'SCHEDULED_BUY'
    target_price = Column(Numeric(10, 2), nullable=True)   # LIMIT_BUY / LIMIT_SELL için zorunlu
    execution_time = Column(DateTime, nullable=True)        # SCHEDULED_BUY için zorunlu (UTC)
    quantity = Column(Numeric(12, 4), nullable=False)
    status = Column(String(20), default="PENDING", nullable=False, index=True)  # PENDING | EXECUTED | CANCELLED | FAILED
    fail_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)

    user = relationship("User")
    stock = relationship("Stock")


# ---------------------------------------------------------------------------
# MODÜL 11: Kişiye Özel Bildirim & Alarm Sistemi
# ---------------------------------------------------------------------------
class StockNotificationPreference(Base):
    """
    Bir kullanıcının belirli bir hisse için bıraktığı alarm tercihleri. Fiyat
    üstü/altı alarmları tek seferliktir (tetiklenince alan None'a döner); %
    değişim ve AI sinyal alarmları günde en fazla bir kez tetiklenir (last_*_date
    ile takip edilir). Kullanıcı başına hisse başına tek satır tutulur.
    """
    __tablename__ = "stock_notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "stock_id", name="uq_notification_pref_user_stock"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    price_above = Column(Numeric(10, 2), nullable=True)
    price_below = Column(Numeric(10, 2), nullable=True)
    pct_change_trigger = Column(Numeric(6, 2), nullable=True)  # örn. 5.0 -> günlük ±%5 hareket
    notify_kap = Column(Boolean, default=False, nullable=False)
    notify_ai_signal = Column(Boolean, default=False, nullable=False)
    last_pct_trigger_date = Column(Date, nullable=True)
    last_ai_signal_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    stock = relationship("Stock")


class Watchlist(Base):
    """Kullanıcının 'Favorilerim/İzleme Listesi'ne eklediği hisseler."""
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_id", "stock_id", name="uq_watchlist_user_stock"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    stock = relationship("Stock")


class Notification(Base):
    """Kullanıcıya özel, sistem içi bildirim geçmişi (fiyat/KAP/AI sinyal alarmlarının çıktısı)."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True)
    notif_type = Column(String(20), nullable=False)  # 'PRICE_ABOVE' | 'PRICE_BELOW' | 'PCT_CHANGE' | 'KAP' | 'AI_SIGNAL'
    title = Column(String(200), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")
    stock = relationship("Stock")
