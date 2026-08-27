# NOT: Birincil anahtar sütunlarında `index=True` KULLANILMAZ. PostgreSQL
# birincil anahtar için zaten benzersiz bir indeks oluşturur; ayrıca index=True
# vermek birebir aynı ikinci bir indeks daha yaratır. Bunlar hiç kullanılmadan
# (0 tarama) her INSERT'te güncelleniyor ve yer kaplıyorlardı — üretimde
# temizlenince 5,3 MB geri alındı. Modelden de kaldırıldı, yoksa bir sonraki
# create_all() hepsini geri getirirdi.
from sqlalchemy import Column, Integer, BigInteger, String, Numeric, Boolean, DateTime, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
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
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    company_name = Column(String(150), nullable=False)
    is_active = Column(Boolean, default=True)
    sector = Column(String(50), nullable=True, index=True)

    # Katılım Endeksi (Helal Finans) Uygunluk Bilgileri
    is_katilim_compliant = Column(Boolean, default=False)
    # Katılım uygunluğunun ÜÇ durumu vardır: uygun, uygun değil ve HENÜZ
    # DEĞERLENDİRİLMEDİ. Katalog 43'ten 165 hisseye çıkarıldığında yeni
    # hisseler için elle küratörlü uygunluk verisi yoktu; bunları "uygun değil"
    # saymak yanlış bilgi vermek olurdu. Boolean üçüncü durumu ifade edemediği
    # için bu alan eklendi: 'UYGUN' | 'UYGUN_DEGIL' | 'BELIRSIZ'.
    katilim_status = Column(String(12), default="BELIRSIZ", nullable=True, index=True)
    # Katılım taramasının hesaplanmış çıktıları (bkz. katilim.py). Elle
    # küratörlü verinin aksine bunlar gerçek bilanço kalemlerinden üretilir.
    katilim_debt_ratio = Column(Numeric(6, 2), nullable=True)    # Finansal borç / toplam varlık (%)
    katilim_asset_ratio = Column(Numeric(6, 2), nullable=True)   # Nakit + finansal yatırımlar / toplam varlık (%)
    katilim_checked_at = Column(DateTime, nullable=True)
    katilim_detail = Column(Text, nullable=True)                 # Kullanıcıya gösterilecek gerekçe
    # UYDURMA VERİ UYARISI: `purification_rate` başlangıçta elle yazılmış bir
    # yer tutucuydu. Ölçüldü — 43 hisseye verilen 31 farklı değer 0,4 ile 3,0
    # arasında neredeyse kusursuz 0,1'lik adımlarla diziliydi; bu bir finansal
    # dağılım değil, aritmetik bir dizidir. Kalan 122 hissede hiç değer yoktu.
    # Yerine KAP'ın resmi "Katılım Finansı İlkeleri Bilgi Formu" verisi geldi
    # (aşağıdaki kap_* alanları, bkz. katilim_kap.py). Bu alan geriye dönük
    # uyumluluk için duruyor; YENİ KOD BUNU KULLANMAMALIDIR.
    purification_rate = Column(Numeric(5, 2), default=0.00)  # BAYAT — kap_* alanlarını kullan
    non_compliance_reason = Column(String, nullable=True)

    # --- KAP Katılım Finansı İlkeleri Bilgi Formu (ŞİRKETİN RESMİ BEYANI) ---
    # Kaynak: kap.org.tr, şirketin kendi bildirdiği form (bkz. katilim_kap.py).
    # Tahmin değil beyandır; bu yüzden kullanıcıya kaynak bağlantısıyla birlikte
    # gösterilebilir.
    kap_katilim_gelir_pct = Column(Numeric(6, 2), nullable=True)   # Uygun olmayan gelirlerin oranı (%)
    kap_katilim_varlik_pct = Column(Numeric(6, 2), nullable=True)  # Uygun olmayan varlıkların oranı (%)
    kap_katilim_borc_pct = Column(Numeric(6, 2), nullable=True)    # Uygun olmayan borçların oranı (%)
    kap_katilim_donem = Column(String(40), nullable=True)          # "2026 / 6 Aylık"
    kap_katilim_url = Column(String(500), nullable=True)           # Kaynak KAP bildirimi
    kap_katilim_updated_at = Column(DateTime, nullable=True)

    # Yahoo Finance'ın resmi "önceki kapanış" referansı (fast_info.previousClose),
    # scheduler her fiyat güncellemesinde tazeler. Günlük % değişim hesabında
    # kendi stock_prices_daily türetmemizden ÖNCE bu kullanılır — BİST'in tedbir/
    # taban-tavan referans fiyatı kurallarını Yahoo bizden daha doğru yansıtıyor
    # (bkz. GUNDG örneği: kendi hesabımız -%18.9 derken gerçek taban -%9.96'ydı).
    previous_close = Column(Numeric(10, 2), nullable=True)
    # Seansın resmi açılış/yüksek/düşük değerleri (Yahoo regularMarketOpen/DayHigh/DayLow).
    # Kendi tik geçmişimizden türetmek yanlış sonuç veriyordu: tikler yalnızca scheduler
    # çalıştığında yazılıyor, dolayısıyla "açılış" gerçekte ilk KAYDEDİLEN fiyat oluyordu
    # (ör. backend 11:15'te yeniden başlarsa açılış 11:15 fiyatı görünüyordu).
    open_price = Column(Numeric(10, 2), nullable=True)
    day_high = Column(Numeric(10, 2), nullable=True)
    day_low = Column(Numeric(10, 2), nullable=True)

    # Relationships
    prices = relationship("StockPrice", back_populates="stock", cascade="all, delete-orphan")
    portfolios = relationship("Portfolio", back_populates="stock")
    bot_logs = relationship("BotLog", back_populates="stock")
    analysis = relationship("CompanyAnalysis", back_populates="stock", uselist=False, cascade="all, delete-orphan")


class StockPrice(Base):
    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    # BigInteger şart: BIST'te yüksek hacimli hisselerde günlük lot adedi Postgres
    # integer (int4) üst sınırını (2.147.483.647) aşıyor ve günlük geçmiş tazeleme
    # 'integer out of range' ile patlıyordu.
    volume = Column(BigInteger, nullable=True)
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

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    trade_date = Column(Date, nullable=False, index=True)
    open = Column(Numeric(12, 2), nullable=True)
    high = Column(Numeric(12, 2), nullable=True)
    low = Column(Numeric(12, 2), nullable=True)
    close = Column(Numeric(12, 2), nullable=False)
    # BigInteger şart: BIST'te yüksek hacimli hisselerde günlük lot adedi Postgres
    # integer (int4) üst sınırını (2.147.483.647) aşıyor ve günlük geçmiş tazeleme
    # 'integer out of range' ile patlıyordu.
    volume = Column(BigInteger, nullable=True)

    stock = relationship("Stock")


class IndexHistory(Base):
    """
    Piyasa endekslerinin (BIST 100 = XU100) günlük kapanış serisi.

    Neden ayrı tablo: endeks bir hisse değildir; stocks tablosuna sahte bir
    satır olarak eklemek onu tarayıcıda/listelerde/portföyde işlem yapılabilir
    gibi gösterme riski taşır. Ayrıca endeks için katılım uygunluğu, bilanço
    analizi gibi alanların hiçbiri anlamlı değildir.

    Kullanıcının portföy getirisini endekse karşı kıyaslamak için kullanılır
    (bkz. /api/portfolio/benchmark).
    """
    __tablename__ = "index_history"
    __table_args__ = (UniqueConstraint("symbol", "trade_date", name="uq_index_symbol_date"),)

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)   # 'XU100'
    trade_date = Column(Date, nullable=False, index=True)
    close = Column(Numeric(14, 2), nullable=False)

    # Gun ici tazeleme alanlari (bkz. tr_market.py, scheduler.refresh_tr_quotes_job).
    # Doviz ve altin gun icinde 15 dakikada bir GUNCELLENIR; bu yuzden bugunun
    # satiri bir "kapanis" degil, en son goruleni tutar. updated_at olmadan
    # arayuz "12:15 itibariyla" diyemez, kullanici da bayat bir sayiyi anlik
    # sanar -- sorunun yarisi tam olarak buydu.
    updated_at = Column(DateTime, nullable=True)
    source = Column(String(20), nullable=True)          # 'truncgil' | 'tcmb' | 'yfinance'
    # Kaynagin KENDI gunluk degisimi. Kendi gecmisimizden hesaplamak, dunku
    # satir baska bir kaynaktan geldiyse yanlis sonuc verirdi.
    change_1d_pct = Column(Numeric(6, 2), nullable=True)


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
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


class Transaction(Base):
    """
    Kullanıcının kendi (bot dışı) gerçekleşmiş alım/satım işlemlerinin kalıcı kaydı.

    Neden ayrı bir tablo: `portfolios` yalnızca AÇIK pozisyonun anlık halini tutar.
    Bir pozisyon tamamen satıldığında satır silindiği için o hissenin alınıp
    satıldığına dair hiçbir iz kalmıyordu — ne işlem geçmişi ne de gerçekleşen
    kâr/zarar hesaplanabiliyordu. Bot tarafında bu izi `bot_logs` tutuyor;
    burası onun kullanıcı tarafındaki karşılığıdır.

    `realized_pnl` yalnızca SAT satırlarında doludur, satış anındaki ortalama
    maliyet üzerinden hesaplanır ve KOMİSYONDAN SONRADIR. Bu değer sonradan
    yeniden hesaplanamaz (ortalama maliyet zamanla değişir), bu yüzden işlem
    anında yazılır.

    `commission` 2026-08-27'de eklendi. Ondan ÖNCEKİ satırlarda NULL'dur —
    o dönem gerçek işlemlerde komisyon hiç kesilmiyordu (backtest kesiyordu,
    bu yüzden kullanıcının kendi işlemleri stratejilerden haksız yere kârlı
    görünüyordu). Geriye dönük düzeltme YAPILMADI: geçmiş bakiye hareketleri
    o günkü kurallara göre gerçekleşti, sonradan değiştirmek işlem geçmişiyle
    bakiyeyi tutarsız hale getirirdi.
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id"), nullable=False, index=True)
    action_type = Column(String(10), nullable=False)  # 'AL' / 'SAT'
    quantity = Column(Numeric(12, 4), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    # BRÜT tutar (adet x fiyat). Komisyon DAHİL DEĞİLDİR — o ayrı kolonda.
    total_amount = Column(Numeric(15, 2), nullable=False)
    # Bu işlemde alınan komisyon (TL). Alımda maliyeti artırır, satımda geliri azaltır.
    commission = Column(Numeric(12, 2), nullable=True)
    # SAT işlemlerinde gerçekleşen kâr/zarar (TL). AL işlemlerinde NULL.
    # KOMİSYONDAN SONRADIR: alım komisyonu average_cost'a gömülü, satım
    # komisyonu birim fiyattan düşülmüş haldedir.
    realized_pnl = Column(Numeric(15, 2), nullable=True)
    # Satış anındaki ortalama maliyet — kullanıcıya "hangi maliyetten sattın" gösterebilmek için.
    average_cost_at_trade = Column(Numeric(10, 2), nullable=True)
    # 'MANUAL': /api/trade üzerinden anlık işlem, 'LIMIT_ORDER': bekleyen emrin gerçekleşmesi.
    source = Column(String(20), default="MANUAL", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="transactions")
    stock = relationship("Stock")


class StockVote(Base):
    """
    Topluluk beklenti anketi (road_map.md #6): kullanıcıların hisse başına
    "Yükselir / Düşer" oyu. Yorum yazmaya göre çok daha düşük sürtünmeli olduğu
    için yorum tabanlı sentiment'ten bağımsız, tek tıkla veri toplar.

    Her kullanıcı bir hisse için TEK oy tutar; tekrar oy verdiğinde mevcut satır
    güncellenir (UNIQUE kısıtı bunu garanti eder). `updated_at` sayesinde
    "son 30 günün oyları" gibi taze bir kesit alınabilir.
    """
    __tablename__ = "stock_votes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # 'UP' / 'DOWN'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "stock_id", name="uq_stock_vote_user_stock"),
    )


class BotLog(Base):
    __tablename__ = "bot_logs"

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    total_portfolio_value = Column(Numeric(15, 2), nullable=False)
    recorded_date = Column(Date, nullable=False, index=True)

    __table_args__ = (UniqueConstraint("user_id", "recorded_date", name="uq_user_perf_user_date"),)


class BotPerformanceHistory(Base):
    __tablename__ = "bot_performance_history"

    id = Column(Integer, primary_key=True)
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

    id         = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
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
    # Temettü: yfinance dividendYield (oransal) yüzdeye çevrilerek saklanır.
    # Portföy temettü geliri projeksiyonu ve hisse kartlarındaki verim rozeti bunu kullanır.
    # Hisse künyesi: 52 hafta bandı, piyasa değeri, ortalama hacim.
    # CompanyAnalysis'te tutulur çünkü bunlar zamanla DEĞİŞEN değerlerdir ve
    # gece analiz işiyle birlikte tazelenir (Stock tablosu ise sabit katalogdur).
    fifty_two_week_high = Column(Numeric(12, 2), nullable=True)
    fifty_two_week_low = Column(Numeric(12, 2), nullable=True)
    market_cap = Column(Numeric(20, 2), nullable=True)
    average_volume = Column(BigInteger, nullable=True)
    dividend_yield = Column(Numeric(6, 2), nullable=True)      # yıllık temettü verimi (%)
    dividend_rate = Column(Numeric(10, 2), nullable=True)      # hisse başına yıllık temettü (TL)
    last_dividend_date = Column(Date, nullable=True)           # son temettü ödeme/kayıt tarihi

    # Bilanço Takvimi: bir sonraki çeyreklik bilanço açıklama tarihi (yfinance tahmini)
    next_earnings_date = Column(Date, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stock = relationship("Stock", back_populates="analysis")


# ---------------------------------------------------------------------------
# MODÜL 3.5: Yabancı Takas Oranı Anlık Görüntüleri (Foreign Holding Trend)
# ---------------------------------------------------------------------------
class FinancialStatement(Base):
    """
    Çeyreklik finansal tablo özeti (gelir tablosu + bilanço + nakit akışı).

    Ücretli platformların (Fintables vb.) öne çıkardığı "finansal tablolar"
    özelliğinin karşılığı; veri yfinance'ta ücretsiz olduğu için burada da
    sunulur. Şirket başına genelde son 6 çeyrek gelir.

    Neden CompanyAnalysis'e değil ayrı tabloya: CompanyAnalysis hisse başına
    TEK satırdır (anlık oranlar), burada ise dönem başına bir satır tutulur.
    """
    __tablename__ = "financial_statements"
    __table_args__ = (UniqueConstraint("stock_id", "period_end", name="uq_financial_stock_period"),)

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    period_end = Column(Date, nullable=False, index=True)

    # Gelir tablosu (TL)
    revenue = Column(Numeric(20, 2), nullable=True)
    gross_profit = Column(Numeric(20, 2), nullable=True)
    operating_income = Column(Numeric(20, 2), nullable=True)
    ebitda = Column(Numeric(20, 2), nullable=True)
    net_income = Column(Numeric(20, 2), nullable=True)

    # Bilanço (TL)
    # Katılım taraması için gerekli iki kalem. Endeksin ölçütü nakit ve
    # finansal yatırımların piyasa değerine oranıdır; bunlar olmadan tarama
    # yalnızca borç ayağıyla yapılabilirdi.
    long_term_debt = Column(Numeric(20, 2), nullable=True)
    current_debt = Column(Numeric(20, 2), nullable=True)
    cash_and_equivalents = Column(Numeric(20, 2), nullable=True)
    short_term_investments = Column(Numeric(20, 2), nullable=True)
    total_assets = Column(Numeric(20, 2), nullable=True)
    total_equity = Column(Numeric(20, 2), nullable=True)
    total_debt = Column(Numeric(20, 2), nullable=True)

    # Nakit akışı (TL)
    operating_cashflow = Column(Numeric(20, 2), nullable=True)
    free_cashflow = Column(Numeric(20, 2), nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    stock = relationship("Stock")


class DividendHistory(Base):
    """
    Hisse başına geçmiş temettü ödemeleri (tarih + hisse başına brüt tutar).

    Katılım finansı odaklı bu uygulamada temettü merkezi bir kavram olduğu için
    yalnızca güncel verim değil ödeme GEÇMİŞİ de tutulur: kullanıcı şirketin
    temettüyü düzenli ödeyip ödemediğini ve tutarın büyüyüp büyümediğini görür.
    """
    __tablename__ = "dividend_history"
    __table_args__ = (UniqueConstraint("stock_id", "pay_date", name="uq_dividend_stock_date"),)

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    pay_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 6), nullable=False)   # hisse başına brüt TL

    stock = relationship("Stock")


class ForeignHoldingSnapshot(Base):
    """
    Her derin analiz tazelemesinde yfinance'tan alınan kurumsal/yabancı sahiplik
    oranının (heldPercentInstitutions, en yakın halka açık proxy) günlük anlık
    görüntüsü. 30/90 günlük değişim trendi bu tablodan hesaplanır — BİST için
    gerçek Takasbank yabancı oranı verisi halka açık/ücretsiz bir API üzerinden
    sağlanmadığından, bu alan en iyi çaba (best-effort) proxy'dir.
    """
    __tablename__ = "foreign_holding_snapshots"

    id = Column(Integer, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, index=True)
    held_pct = Column(Numeric(6, 2), nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)

    stock = relationship("Stock")


# ---------------------------------------------------------------------------
# MODÜL 4: İçeriden Öğrenenlerin Ticareti (Insider Trades)
# ---------------------------------------------------------------------------
class InsiderTrade(Base):
    __tablename__ = "insider_trades"

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    fund_type = Column(String(50), nullable=True)
    risk_level = Column(Integer, nullable=True)  # 1-7 (TEFAS risk skalası)
    is_katilim_compliant = Column(Boolean, default=False)

    prices = relationship("FundPrice", back_populates="fund", cascade="all, delete-orphan")


class FundPrice(Base):
    __tablename__ = "fund_prices"

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
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
class PushSubscription(Base):
    """
    Bir tarayıcının/cihazın Web Push aboneliği.

    Kullanıcı başına BİRDEN FAZLA satır olabilir: telefon, tablet ve masaüstü
    ayrı abonelikler üretir; aynı kullanıcı hepsinden bildirim almalıdır.
    Benzersizlik `endpoint` üzerindedir çünkü tarayıcının verdiği endpoint URL'i
    aboneliğin gerçek kimliğidir.

    iOS NOTU: Safari yalnızca ANA EKRANA EKLENMİŞ (standalone) PWA'larda push
    aboneliğine izin verir — normal Safari sekmesinde `Notification.requestPermission`
    çağrısı bile başarısız olur. Bu yüzden arayüz iOS'ta önce kurulum ister.
    """
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(100), nullable=False)
    user_agent = Column(String(300), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_success_at = Column(DateTime, nullable=True)
    # Üst üste başarısız gönderim sayısı. Push servisi 404/410 dönerse abonelik
    # zaten silinir; bu sayaç geçici hataların (ağ, 5xx) üst üste birikmesini
    # yakalamak için tutulur.
    failure_count = Column(Integer, default=0, nullable=False)

    user = relationship("User")


class StockNotificationPreference(Base):
    """
    Bir kullanıcının belirli bir hisse için bıraktığı alarm tercihleri. Fiyat
    üstü/altı alarmları tek seferliktir (tetiklenince alan None'a döner); %
    değişim ve AI sinyal alarmları günde en fazla bir kez tetiklenir (last_*_date
    ile takip edilir). Kullanıcı başına hisse başına tek satır tutulur.
    """
    __tablename__ = "stock_notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "stock_id", name="uq_notification_pref_user_stock"),)

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    # Kullanıcının kendi hedef fiyatı ve notu — "bunu 120 TL'den almayı düşünüyorum,
    # bilanço sonrası tekrar bak" gibi. Alarm sisteminden (StockNotificationPreference)
    # ayrıdır: burası bildirim üretmez, yalnızca kullanıcının kendi takip notudur.
    target_price = Column(Numeric(10, 2), nullable=True)
    note = Column(String(280), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    stock = relationship("Stock")


class Notification(Base):
    """Kullanıcıya özel, sistem içi bildirim geçmişi (fiyat/KAP/AI sinyal alarmlarının çıktısı)."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="SET NULL"), nullable=True)
    notif_type = Column(String(20), nullable=False)  # 'PRICE_ABOVE' | 'PRICE_BELOW' | 'PCT_CHANGE' | 'KAP' | 'AI_SIGNAL'
    title = Column(String(200), nullable=False)
    message = Column(String(500), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User")
    stock = relationship("Stock")
