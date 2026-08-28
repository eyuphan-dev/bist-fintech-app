# BIST Sanal Borsa Simülatörü

Borsa İstanbul hisseleri için **gerçek para kullanılmayan** bir yatırım
simülatörü. Kullanıcı sanal bakiyeyle başlar, gerçek fiyatlarla alım-satım
yapar ve ücretli terminallerde para karşılığı sunulan analiz araçlarına
ücretsiz erişir.

**Canlı:** https://borsa-trader.duckdns.org

---

## Amaç

Borsaya yeni başlayan biri iki şeyle aynı anda uğraşmak zorunda kalıyor:
riski öğrenmek ve para kaybetmek. Bu uygulama ikincisini denklemden çıkarıyor
— aynı verilerle, aynı araçlarla, ama sanal bakiyeyle.

İkinci ve asıl ayırt edici amaç: **katılım (faizsiz) finans odağı.**
Türkiye'de katılım hassasiyeti olan yatırımcı, bir hissenin uygun olup
olmadığını genelde bir listeye bakarak öğreniyor — listenin neye dayandığını
göremeden. Burada uygunluk bir rozetle geçiştirilmiyor, **kaynağı gösteriliyor.**

Projenin temel ilkesi: **bilinmeyen bir şey uydurulmaz.**
Veri yoksa oran gösterilmez, "değerlendirilmedi" denir. Bir oran gösteriliyorsa
kapsamı da gösterilir. Hesaplanan her sayının arkasında ya bir kaynak bağlantısı
ya da ölçülmüş bir doğrulama vardır.

---

## Mimari

Tek VPS üzerinde iki pm2 süreci. Konteyner yok, Kubernetes yok, mesaj kuyruğu
yok — bu ölçekte gerekmiyor.

```mermaid
flowchart TD
    U["Kullanıcı<br/>tarayıcı · iOS/Android PWA"]
    N["nginx · Let's Encrypt<br/>borsa-trader.duckdns.org"]
    F["borsa-frontend<br/>Next.js 16 · pm2 · :3000"]
    B["borsa-backend<br/>FastAPI · uvicorn · pm2 · :4000"]
    S["APScheduler<br/>aynı süreç içinde"]
    D[("PostgreSQL 16<br/>bist_app")]
    Y["Yedekleme<br/>GPG/AES256 · GitHub Actions"]

    U -->|HTTPS| N
    N -->|"/"| F
    N -->|"/api/*"| B
    F -->|"sunucu tarafı çağrı"| B
    B <--> D
    S --> D
    B -.->|"aynı süreç"| S
    D -->|"her gece 03:30 UTC"| Y
```

> **Neden tek uvicorn işçisi:** sinyal önbelleği süreç içi bir Python sözlüğü.
> Çok işçiye çıkılırsa her işçinin ayrı önbelleği olur ve aynı istek farklı
> sonuç döndürür. Ölçeklemeden önce önbellek dışarı taşınmalı.

### Veri akışı

Uygulama **kullanıcı isteği sırasında hiçbir dış servise bağlanmaz.** Tüm dış
çağrılar zamanlanmış işlerde yapılır, sonuç veritabanına yazılır, API uçları
yalnızca veritabanından okur. Bu yüzden Yahoo yavaşladığında site yavaşlamaz.

```mermaid
flowchart LR
    subgraph DIS["Dış kaynaklar"]
        Y["Yahoo Finance<br/>(proxy zorunlu)"]
        T["truncgil / TCMB"]
        K["KAP"]
        TE["TEFAS"]
        R["9 Türkçe RSS"]
        H["halkarz.com"]
    end

    S["APScheduler<br/>zamanlanmış işler"]
    D[("PostgreSQL")]
    A["/api/*<br/>yalnızca okuma"]
    U["Kullanıcı"]

    Y --> S
    T --> S
    K --> S
    TE --> S
    R --> S
    H --> S
    S -->|yazar| D
    D -->|okur| A
    A --> U
```

| İş | Sıklık | Ne çeker |
|---|---|---|
| `bist_updater` | Hafta içi 10:00–18:55, 5 dk | Hisse fiyatları |
| `tr_quotes_sync` | 15 dakika, 7/24 | Dolar, euro, gram altın, BIST 100 |
| `market_data_sync` | Günlük 08:00 UTC | KAP, TEFAS, haberler, temettü, halka arz, katılım formları |
| `deep_analysis_sync` | Günlük 02:00 UTC | En bayat 40 hissenin bilanço analizi |
| `stock_news_sync` | Günlük 07:30 UTC | Hisse haberleri |
| `log_cleaner` | Pazar 03:00 UTC | 90 günden eski loglar |

---

## Katılım uygunluğu nasıl belirleniyor

Bu, uygulamanın en çok emek verilen kısmı ve üç katmanlı:

```mermaid
flowchart TD
    A["KAP — Katılım Finansı<br/>İlkeleri Bilgi Formu"] -->|"şirketin RESMÎ beyanı"| B["Uygun olmayan<br/>gelir / varlık / borç oranları"]
    C["Bilanço<br/>(yfinance)"] -->|"hesaplanan ön tarama"| D["Finansal borç ve nakit<br/>oranları"]
    E["Elle küratörlü liste"] --> F["UYGUN / UYGUN DEĞİL /<br/>DEĞERLENDİRİLMEDİ"]

    B --> G["Kullanıcıya gösterilen"]
    D --> G
    F --> G
    B -->|"beyan eşiği aşıyorsa"| H["Çelişki uyarısı"]
    F --> H
```

- **Resmî beyan birinci kaynak.** 165 hissenin **147'sinde** KAP'a bildirilmiş
  form var; oranlar dönem bilgisi ve kaynak bağlantısıyla gösteriliyor.
- **Hesaplanan tarama karar vermez.** Elle küratörlü listeyle uyumu ölçüldü
  (%69) ve yetersiz bulundu; yalnızca oranları ve sınıra uzaklığı gösteriyor.
- **Çelişki gizlenmiyor.** Bir hisse "uygun" işaretliyken kendi beyanı eşiği
  aşıyorsa arayüz bunu açıkça uyarıyor. Ölçülen uyum: 38 hissede 29 (%76).
  Bu oran otomatik damga vurmaya yetmediği için karar kullanıcıya bırakılıyor.

Portföy düzeyinde ayrıca **katılım uyum karnesi** var: değerin yüzde kaçı
uygun, ağırlıklı arındırma oranı ne — ve o oranın portföyün ne kadarını
kapsadığı.

---

## "AI botu" nasıl çalışıyor

Açık olalım: **burada bir dil modeli (LLM) yok.** Arayüzdeki "AI botu",
teknik göstergeler üzerine kurulu **kural tabanlı bir strateji motoru.**
Ne yaptığı tamamen okunabilir ve denetlenebilir — kara kutu değil.

```mermaid
flowchart TD
    A["Günlük OHLCV barları<br/>(kendi veritabanımız)"] --> B["Süreye göre yeniden örnekleme"]
    B --> C{"Strateji süresi"}
    C -->|"1G — Scalp"| D["RSI(7) + EMA9/EMA21<br/>momentum"]
    C -->|"1H — Swing"| E["MACD kesişimi +<br/>destek/direnç kırılımı"]
    C -->|"1A — Trend"| F["SMA20/SMA50 kesişimi +<br/>Piotroski barajı"]
    D --> G["Sinyal + güven skoru"]
    E --> G
    F --> G
    G --> H{"Güven ≥ risk modu eşiği?"}
    H -->|Hayır| I["İşlem yok"]
    H -->|Evet| J{"Borsa açık mı?"}
    J -->|Hayır| I
    J -->|Evet| K["AL / SAT<br/>+ stop-loss / take-profit"]
```

Risk modu, sinyalin ne kadar kolay tetikleneceğini belirler:

| Mod | Asgari güven | Stop-loss | Take-profit | RSI eşikleri |
|---|---|---|---|---|
| 🐢 Yavaş | 0,85 | %2,5 | %5,0 | 25 / 75 |
| ⚖️ Normal | 0,65 | %4,5 | %9,0 | 30 / 70 |
| 🚀 Agresif | 0,20 | %8,0 | %16,0 | 38 / 62 |

Bot yalnızca **hafta içi 10:00–18:15** arasında işlem yapar; borsa kapalıyken
hiçbir emir üretmez.

Aynı motor "sinyal taraması" sayfasını da besler. Bir tasarım ayrıntısı:
altın kesişim gibi olaylar **bir kez** gerçekleşir, ama "SMA50 > SMA200"
koşulu kesişimden sonra aylarca doğru kalır. Koşulu doğrudan raporlamak,
aylar önce olmuş bir kesişimi her gün "yeni sinyal" diye göstermek olurdu.
Bu yüzden kesişim sinyalleri, koşulun **bugün doğru ve dün yanlış** olmasına
göre üretilir.

---

## Öne çıkan özellikler

**Analiz**
- Katılım uygunluk taraması ve KAP beyan oranları
- Piotroski F-Skoru, analist konsensüsü, finansal tablolar
- Strateji backtest'i, DCA simülasyonu, mevsimsellik
- Pivot / Fibonacci seviyeleri, Stochastic, ADX, OBV
- Hisse tarayıcı (F/K, PD/DD, ROE, temettü verimi, sektör, katılım)

**Piyasa verisi**
- Dolar, euro, gram altın — 15 dakikada bir, yerli kaynaktan
- 9 Türkçe kaynaktan piyasa haber akışı
- KAP bildirimleri, önemli pay sahibi hareketleri, içeriden öğrenen işlemleri
- Temettü takvimi — yaklaşan nakit ödemeler, tutar ve brüt verimle
- Halka arz takvimi — fiyat, talep toplama tarihleri, dağıtım yöntemi
- TEFAS katılım fonları (390 fon)

**Portföy**
- Performans karnesi: isabet oranı, ortalama tutma süresi
- Risk paneli, XU100 kıyası, karşı-olgusal analiz ("ya hiç almasaydım")
- Temettü geliri projeksiyonu, katılım uyum karnesi
- Bekleyen limit emirleri, kişisel işlem botu

**Diğer**
- Web push bildirimleri (fiyat alarmı, temettü, KAP), PWA
- Favori listesi, hisse karşılaştırma, ısı haritası, topluluk yorumları

---

## Kullanılan teknolojiler

| Katman | Teknoloji | Not |
|---|---|---|
| Backend | **FastAPI**, Pydantic v2 | Uçlar şemayla doğrulanır |
| ORM | **SQLAlchemy 2** | |
| Veritabanı | **PostgreSQL 16** (üretim) · SQLite (yerel) | `DATABASE_URL` yoksa SQLite |
| Zamanlayıcı | **APScheduler** | Backend süreci içinde |
| Frontend | **Next.js 16** (App Router, Turbopack) | |
| Stil | **TailwindCSS 4** | |
| Grafik | ApexCharts | |
| İkon | lucide-react | |
| Teknik analiz | `ta`, pandas, numpy | |
| Piyasa verisi | yfinance | Proxy zorunlu (aşağıya bak) |
| Süreç yönetimi | pm2 | İki süreç: frontend + backend |
| Sunucu | nginx (aaPanel) · Let's Encrypt | DigitalOcean VPS |
| CI/CD | GitHub Actions | Test + otomatik deploy |

> **yfinance neden proxy üzerinden:** veri merkezi IP'leri (bizimki
> DigitalOcean Frankfurt) çok sayıda yfinance kullanıcısı tarafından
> paylaşıldığı için Yahoo tarafında kalıcı olarak engellendi — basit hız
> sınırından farklı, kendiliğinden açılmıyor. `YF_PROXY_URL` olmadan üretimde
> hisse fiyatı hiç gelmez. Truncgil, TCMB, KAP ve TEFAS proxy gerektirmez.

---

## Veri sağlığı

`GET /api/health` dokuz veri hattının satır sayısını ve tazeliğini raporlar.

Bu uç, **"kod patlamıyor ama veri sessizce gelmiyor"** sınıfı arızalar için
var. Bunlar hata logu üretmez — 200 dönen boş yanıtlardır ve elle kazmadan
fark edilmezler. Her hattın tazelik eşiği, onu besleyen işin çalışma
sıklığından türetilmiştir.

---

## Kurulum

### Gereksinimler

- Python **3.9+** (üretimde 3.12)
- Node.js **20+**
- PostgreSQL 16 — *isteğe bağlı;* yoksa yerelde SQLite kullanılır

### Backend

```bash
cd backend
python -m venv venv

# Windows
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe -m uvicorn main:app --reload --port 4000

# macOS / Linux
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 4000
```

İlk açılışta veritabanı tabloları otomatik oluşturulur ve 165 hisselik
katalog tohumlanır (`init_db.py`). İşlem idempotenttir; her açılışta güvenle
tekrarlanır.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Varsayılan olarak `http://localhost:4000/api` adresine bağlanır. Farklı bir
adres için `frontend/.env.local` içine:

```
NEXT_PUBLIC_API_URL=http://localhost:4000/api
```

### Ortam değişkenleri

| Değişken | Zorunlu | Ne işe yarar |
|---|---|---|
| `JWT_SECRET_KEY` | **Evet** | Oturum token'larını imzalar |
| `DATABASE_URL` | Hayır | Yoksa SQLite. Örn. `postgresql://kullanici:sifre@localhost/bist_app` |
| `YF_PROXY_URL` | Üretimde evet | Yahoo Finance erişimi |
| `FRONTEND_URL` | Hayır | CORS izinleri |
| `DISABLE_SCHEDULER` | Hayır | `1` ise zamanlanmış işler çalışmaz (test/CI) |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Hayır | Web push bildirimleri |

---

## Test

```bash
cd backend
python -m uvicorn main:app --port 4000     # ayrı bir terminalde
python smoke_test.py                       # 101 test
```

Duman testi kimlik doğrulamadan işlem kurallarına, veri hatlarından güvenlik
sınırlarına kadar her özelliği tek tek çalıştırır. Salt-okunur uçlar üretime,
yazan uçlar yerele gider — testin üretim veritabanına kullanıcı ya da işlem
yazması kabul edilemez.

CI modunda her şey yerel bir örneğe koşar:

```bash
DISABLE_SCHEDULER=1 python -m uvicorn main:app --port 4000
SMOKE_CI=1 python smoke_test.py
```

Her push'ta GitHub Actions duman testini **Python 3.9 ve 3.12** üzerinde
koşar ve ön yüzü derler. İki sürüm birden test edilir çünkü üretim 3.12,
geliştirme makinesi 3.9 çalışıyor ve kod ikisinde de çalışmak zorunda.

---

## Dizin yapısı

```
backend/
  main.py               API uçları
  models.py             SQLAlchemy modelleri
  schemas.py            Pydantic şemaları
  scheduler.py          Zamanlanmış işler
  bot.py                Kural tabanlı strateji motoru
  signals.py            Teknik sinyal taraması
  analysis_engine.py    Bilanço analizi, Piotroski
  katilim*.py           Katılım uygunluğu (KAP + hesaplanan)
  temettu_takvimi.py    KAP'tan temettü ödemeleri
  haber_*.py            Türkçe haber çekme ve eşleştirme
  veri_sagligi.py       /api/health
  smoke_test.py         101 testlik duman testi

frontend/src/app/
  page.tsx              Ana sayfa (portföy)
  hisse/[symbol]/       Hisse detay
  components/           Paylaşılan bileşenler
```

---

> **Yatırım tavsiyesi değildir.** Gerçek para kullanılmaz, veriler en az
> 15 dakika gecikmelidir.
>
> Design by Eyüphan İpek
