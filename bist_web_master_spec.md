# BIST Takip, Derin Bilanço Analizi, Helal Finans & Kişiselleştirilmiş AI Quant Trader Web Uygulaması
## Uçtan Uca Master Proje, Mimari, UI/UX ve Teknik Şartname Rehberi (v6 - Tam Sürüm)

Bu doküman; projenin konseptinden teknik altyapısına, SQLite3 veritabanı mimarisinden Python backend iş mantıklarına, "Anti-AI Blue" tasarım sisteminden mobil optimizasyona, çalışır durumdaki Derin Bilanço Analizi hesaplama motorlarından kişiselleştirilmiş AI Quant Botu ve hukuki sorumluluk reddi mekanizmalarına kadar **en başından beri geliştirilen tüm mimariyi tek bir çatı altında toplamaktadır.**

---

## İÇİNDEKİLER
1. [Proje Özeti ve Genel Mimari](#1-proje-özeti-ve-genel-mimari)
2. [Tasarım Sistemi, UI/UX & Mobil Optimizasyon ("Anti-AI Blue")](#2-tasarım-sistemi-uiux--mobil-optimizasyon-anti-ai-blue)
3. [SQLite3 Veritabanı Şeması (`schema.sql`)](#3-sqlite3-veritabanı-şeması-schemasql)
4. [BİST Veri Akışı, Katalog & Borsa Seans Kontrolü](#4-bist-veri-akışı-katalog--borsa-seans-kontrolü)
5. [Kişiselleştirilmiş Multi-Tenant AI Bot & Özel Sanal Bakiye](#5-kişiselleştirilmiş-multi-tenant-ai-bot--özel-sanal-bakiye)
6. [Derin Bilanço Analizi & Matematiksel Hesaplama Motorları](#6-derin-bilanço-analizi--matematiksel-hesaplama-motorları)
7. [Helal Finans (BİST XKTUM Katılım Endeksi), KAP ve TEFAS](#7-helal-finans-bist-xktum-katılım-endeksi-kap-ve-tefas)
8. [Katma Değerli Modüller (Patron Takibi, Sentiment, Döviz/Faiz)](#8-katma-değerli-modüller-patron-takibi-sentiment-dövizfaiz)
9. [Kullanıcı İşlem Logları & 90 Günlük Otomatik Temizlik](#9-kullanıcı-işlem-logları--90-günlük-otomatik-temizlik)
10. [Frontend Bileşenler Şartnamesi (Next.js & TailwindCSS)](#10-frontend-bileşenler-şartnamesi-nextjs--tailwindcss)
11. [Hukuki Zırh: YTD, KVKK, Feragatname ve Sorumluluk Reddi](#11-hukuki-zırh-ytd-kvkk-feragatname-ve-sorumluluk-reddi)
12. [Canlıya Alma (Deployment) ve Yayınlama Mimarisi (0 TL)](#12-canlıya-alma-deployment-ve-yayınlama-mimarisi-0-tl)

---

## 1. Proje Özeti ve Genel Mimari

Bu platform; Borsa İstanbul (BİST) verilerini 15 dakika gecikmeli ve ücretsiz olarak işleyen, profesyonel **Derin Bilanço Analizleri** sunan, Katılım Endeksi (Helal Finans) süzgecine sahip, **her kullanıcıya özel otonom al-sat yapan kişisel Yapay Zeka Botu** barındıran ve kullanıcıların kendi belirledikleri sanal bakiye ile yarışabildiği mobil uyumlu bir web uygulamasıdır.

### Temel Mimari Prensipler
*   **0 TL Veri & Altyapı Maliyeti:** Yahoo Finance API (`.IS` sembolleri) ile 15 dakika gecikmeli veri akışı. PostgreSQL yerine **SQLite3** tercihiyle ek veritabanı sunucusu gerektirmeyen hafif yapı (0 TL Free Tier).
*   **Esnek Sanal Bakiye (Paper Trading):** Kullanıcı hem kendi hesabına hem de kişisel botuna dilediği miktarda sanal bakiye (örn: 50.000 TL, 250.000 TL) tanımlayabilir veya bakiyeyi sıfırlayabilir.
*   **Çoklu Kullanıcı Desteği (Multi-tenant Bot):** Genel tek bir bot yerine, her üyenin kendisine ait bağımsız strateji, bakiye ve portföye sahip kişisel bir Yapay Zeka Botu bulunur.
*   **Teknoloji Yığını:** Next.js 14+ (App Router), TailwindCSS, Python (FastAPI), SQLite3 (`bist_app.db`), Lucide-React.

---

## 2. Tasarım Sistemi, UI/UX & Mobil Optimizasyon ("Anti-AI Blue")

### 2.1. Renk Paleti (Obsidian Dark & Kehribar Gold)
Piyasadaki jenerik elektrik mavisi (`#0066FF`) ve mor parlamalar yerine **Obsidyen Siyahı ve Sıcak Kehribar Gold** tonları kullanılmıştır:

*   **Canvas / Arka Plan:** `#0B0E14` (Obsidyen Siyahı)
*   **Kart Yüzeyi (Surface):** `#151921` (Koyu Kömür)
*   **Sınır / Çizgiler (Border):** `#242B35` (Muted Slate)
*   **Yükseliş / Kâr (Positive):** `#10B981` (Zümrüt Yeşili)
*   **Düşüş / Zarar (Negative):** `#F43F5E` (Koyu Gül Kırmızı)
*   **Vurgu / Bot (Accent):** `#F59E0B` (Sıcak Kehribar Gold)
*   **Birincil Metin:** `#F8FAFC` | **İkincil Metin:** `#8A99AD`

### 2.2. Arayüz ve Tipografi Kuralları
*   ❌ Sihirli değnek (🪄), ışıltı (✦), robot (🤖), beyin (🧠) ikonları **KESİNLİKLE YASAKTIR**.
*   ✅ Yalnızca **Lucide-React** kütüphanesinden 1.5px ince çizgisel ikonlar ve canlı durum noktaları (Status Dots).
*   ✅ Hisse fiyatlarında rakam kaymasını önlemek için CSS: `font-variant-numeric: tabular-nums;`.

### 2.3. Mobil Optimizasyon Standartları
*   **Bottom Navigation Bar (`md:hidden`):** Mobil ekranlarda ekranın altında sabit kalan Midas tarzı alt gezinme barı (Home, BİST, Bot, Fonlar, Portföy).
*   **Touch Targets:** Tüm butonlar ve tıklanabilir kartlar için minimum **44x44px** dokunma alanı.
*   **Responsive Tables:** Derin analiz tabloları mobilde yumuşak yatay kaydırma (`overflow-x-auto WebkitOverflowScrolling: touch`) ile sunulur.

---

## 3. SQLite3 Veritabanı Şeması (`schema.sql`)

```sql
-- 1. Kullanıcılar Tablosu
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    virtual_balance REAL DEFAULT 100000.00,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 2. Kişisel AI Bot Yapılandırması (Kullanıcıya Özel Bot)
CREATE TABLE IF NOT EXISTS user_bots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL,       -- Her kullanıcının 1 kişisel botu olur
    bot_name TEXT DEFAULT 'Kişisel AI Trader',
    virtual_balance REAL DEFAULT 100000.00, -- Botun Özel Sanal Bakiyesi
    is_active INTEGER DEFAULT 1,           -- 1: Aktif, 0: Durduruldu
    risk_profile TEXT DEFAULT 'BALANCED',  -- CONSERVATIVE, BALANCED, AGGRESSIVE
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 3. Hisseler ve Katılım Endeksi (BİST Katalog)
CREATE TABLE IF NOT EXISTS stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT UNIQUE NOT NULL,
    company_name TEXT NOT NULL,
    is_katilim_compliant INTEGER DEFAULT 0, -- 0: Uygun Değil, 1: Uygun (XKTUM)
    purification_rate REAL DEFAULT 0.00,    -- Arınma Oranı (%)
    non_compliance_reason TEXT,
    is_active INTEGER DEFAULT 1
);

-- 4. Geçmiş Fiyat Verileri (Grafikler ve ML)
CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    price REAL NOT NULL,
    volume INTEGER,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_stock_prices_time ON stock_prices(stock_id, recorded_at DESC);

-- 5. Portföyler (Hem Kullanıcı Hem de Kişisel Bot Portföyleri)
CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,            -- Kullanıcı ID
    is_bot_portfolio INTEGER DEFAULT 0,  -- 0: Kullanıcı Portföyü, 1: Bot Portföyü
    stock_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    average_cost REAL NOT NULL,
    UNIQUE(user_id, is_bot_portfolio, stock_id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(stock_id) REFERENCES stocks(id)
);

-- 6. Derin Bilanço Analizi İstatistik Tablosu
CREATE TABLE IF NOT EXISTS company_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER UNIQUE NOT NULL,
    piotroski_score INTEGER,      -- 0-9 Bilanço Sağlık Skoru
    pe_ratio REAL,                -- F/K (Fiyat / Kazanç)
    pb_ratio REAL,                -- PD/DD (Piyasa Değeri / Defter Değeri)
    ev_ebitda REAL,               -- FD/FAVÖK
    sector_pe_avg REAL,           -- Sektör F/K Ortalaması
    fair_value REAL,              -- Graham / DCF Tahmini Makul Eder Fiyat
    discount_rate REAL,           -- İskonto / Potansiyel (%)
    roe REAL,                     -- Özkaynak Karlılığı (%)
    gross_margin REAL,            -- Brüt Kar Marjı (%)
    net_margin REAL,              -- Net Kar Marjı (%)
    fx_exposure_text TEXT,        -- Döviz Duyarlılık Açıklaması
    interest_sensitivity_text TEXT,-- Faiz Duyarlılık Açıklaması
    updated_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

-- 7. Patron / Şirket İçi İşlem Takibi (Insider Trading)
CREATE TABLE IF NOT EXISTS insider_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    symbol TEXT NOT NULL,
    title_person TEXT,
    trade_type TEXT NOT NULL, -- 'BUY' veya 'SELL'
    quantity REAL,
    price REAL,
    trade_date TEXT NOT NULL,
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

-- 8. KAP Bildirimleri
CREATE TABLE IF NOT EXISTS kap_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER,
    symbol TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    kap_url TEXT,
    publish_date TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

-- 9. TEFAS Yatırım Fonları ve Fiyatları
CREATE TABLE IF NOT EXISTS funds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    fund_type TEXT NOT NULL,
    risk_level INTEGER,
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

-- 10. Halka Arz Takvimi
CREATE TABLE IF NOT EXISTS ipos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    symbol TEXT,
    offer_price REAL,
    demand_collection_dates TEXT,
    is_katilim_compliant INTEGER DEFAULT 0,
    lot_distribution_type TEXT
);

-- 11. Yorumlar ve Sentiment Skorları
CREATE TABLE IF NOT EXISTS stock_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    stock_id INTEGER NOT NULL,
    comment_text TEXT NOT NULL,
    sentiment_score REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(stock_id) REFERENCES stocks(id) ON DELETE CASCADE
);

-- 12. Kullanıcı İşlem Logları (Max 90 Günlük)
CREATE TABLE IF NOT EXISTS user_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT,
    ip_address TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 13. Kişisel Bot İşlem Geçmişi
CREATE TABLE IF NOT EXISTS bot_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,             -- Botun Bağlı Olduğu Kullanıcı ID
    stock_id INTEGER NOT NULL,
    action_type TEXT NOT NULL,             -- 'BUY' / 'SELL'
    price REAL NOT NULL,
    quantity REAL NOT NULL,
    reason_text TEXT,                     -- Botun İşlem Gerekçesi
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(stock_id) REFERENCES stocks(id)
);

---

## 13. Kişisel AI Bot Çalışma Süresi & Zaman Dilimi Stratejileri

Kullanıcı kişisel AI Botunu başlatırken çalışacağı zaman dilimini ve strateji süresini seçer:

*   **1 Günlük (Gün İçi / Scalping - `1D`):** 5/15 dakikalık grafikleri tarar. Hızlı RSI ve momentum takibi yapar. Dar Stop-Loss (%1.5) ile gün içi al-sat yapıp süre sonunda pozisyonları kapatır.
*   **1 Haftalık (Swing Trading - `1W`):** 1/4 saatlik grafikleri ve MACD kırılımlarını izler. Orta vadeli dalga hareketlerini yakalamaya çalışır.
*   **1 Aylık (Trend / Pozisyon - `1M`):** Günlük grafikleri, 20/50 günlük hareketli ortalamaları ve Piotroski bilanço skorunu analiz eder. Trend boyunca hisseyi taşır.
*   **Otomatik Süre Takibi:** Veritabanındaki `ends_at` süresi dolduğunda bot çalışmayı durdurur ve kullanıcıya özet performans raporu sunar.

---

## 14. Hafta Sonu İşlem Kısıtlaması & Sabit Fiyat Portföy Doğrulaması

*   **Mutlak Seans Kontrolü (Manual & Bot):** Hafta sonları (Cumartesi - Pazar) ve hafta içi seans dışı saatlerde (18:15 - 10:00) hem kullanıcıların hem de AI Bot'un sanal alım-satım yapması tamamen engellenmiştir. Sistem "Borsa kapalı" uyarısı döndürür.
*   **Portföy Değer Tutarlılığı:** Borsa kapalıyken hisse fiyatları Cuma günkü son kapanış fiyatında sabit kalır. Bakiye veya portföy değerinin durduk yere değişmesini önlemek için toplam portföy değeri strictly `Net Bakiye + (Lot Adedi * Son Kapanış Fiyatı)` formülüyle dondurulur.

---

## 15. Çoklu Cihaz Optimizasyonu & Production Güvenlik Zırhı

### 15.1. Responsive Cihaz Mimarisi
*   **Mobil (< 768px):** Sabit alt navigasyon (`MobileBottomNav`), tek kolonlu akış, iOS çentik ve alt çizgi uyumu (`safe-area-inset`).
*   **Tablet (768px - 1024px):** 2 Kolonlu esnek grid yapısı; grafikler üstte, Midas tarzı derin analiz kartları yan yana.
*   **Masaüstü (> 1024px):** 3 Kolonlu profesyonel borsa terminali düzeni (Sol: Takip Listesi, Orta: Canlı Grafik ve Bilanço, Sağ: Kişisel Bot & Emir Paneli). Alt navigasyon gizlenir.
*   **Mobil İnfaz Önleme:** Mobil cihazlarda metin kutularına odaklanıldığında ekranın istemsiz yakınlaşmasını (zoom) önlemek için minimum 16px font boyutu standardı.

### 15.2. Güvenlik & Yetkisiz Erişim Koruması (Vercel / Render Hardening)
*   **Sıfır Güven (Zero-Trust Payload):** API isteklerinde gelen `user_id` bilgisine asla güvenilmez; tüm yetkiler doğrulanmış JWT token/oturum üzerinden okunur. Kullanıcılar yalnızca kendi bakiyelerini ve kendi kişisel botlarını yönetebilir.
*   **Atomik İşlem Güvenliği (Double-Spending Koruması):** Sanal bakiye düşüşleri ve alım-satım emirleri SQLite `BEGIN IMMEDIATE` işlemleriyle kilitlenir. Negatif lot veya geçersiz sayısal değerler (NaN, Infinity) Pydantic/Zod şemalarıyla engellenir.
*   **API Hız Limiti (Rate Limiting):** Render sunucusunun çökmesini ve spam emirleri engellemek için IP/Kullanıcı bazlı kısıtlama:
    *   Alım/Satım Emirleri: Dakikada maksimum 10 işlem.
    *   Bakiye Sıfırlama: Dakikada maksimum 3 işlem.
    *   Bilanço Tazeleme: Dakikada maksimum 5 işlem.
*   **SQL Injection & XSS Koruması:** Veritabanı sorgularında parametrik ORM yapısı kullanılır. Yorum alanlarındaki kullanıcı metinleri XSS temizliğinden (sanitization) geçirilerek veritabanına yazılır.
*   **Sıkılaştırılamış CORS Politikası:** Canlı ortamda backend CORS izinleri yalnızca Vercel domain'ine (`NEXT_PUBLIC_FRONTEND_URL`) sınırlandırılır.