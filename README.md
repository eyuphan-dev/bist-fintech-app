# BIST Sanal Borsa Simülatörü

Borsa İstanbul hisseleri için **gerçek para kullanılmayan** bir yatırım
simülatörü. Kullanıcı sanal bakiyeyle başlar, gerçek fiyatlarla alım-satım
yapar ve ücretli terminallerde para karşılığı sunulan analiz araçlarına
ücretsiz erişir.

**https://borsa-trader.duckdns.org**

---

## Ne farklı

Uygulamanın odağı **katılım (faizsiz) finans**. Diğer simülatörlerden ayrıldığı
yer, uygunluğu bir rozetle geçiştirmek yerine **kaynağını göstermesi**:

- Katılım oranları şirketlerin **KAP'a bildirdiği resmî beyandan** okunur
  ("Katılım Finansı İlkeleri Bilgi Formu") — uygun olmayan gelir / varlık /
  borç oranları, dönem bilgisi ve kaynak bildirimin bağlantısıyla birlikte.
  Kapsam: **165 hissenin 147'si**.
- Bir hisse "uygun" işaretli ama kendi beyanı eşiği aşıyorsa arayüz bunu
  **açıkça uyarı olarak gösterir** ve kararı kullanıcıya bırakır.
- Portföy düzeyinde **katılım uyum karnesi**: değerin yüzde kaçı uygun,
  ağırlıklı arındırma oranı ne — ve o oranın portföyün ne kadarını kapsadığı.

Genel ilke: **bilinmeyen bir şey uydurulmaz.** Veri yoksa oran gösterilmez,
"değerlendirilmedi" denir.

## Öne çıkan özellikler

**Analiz**
- Katılım (faizsiz) uygunluk taraması ve KAP beyan oranları
- Piotroski F-Skoru, analist konsensüsü, finansal tablolar
- Strateji backtest'i, DCA simülasyonu, mevsimsellik
- Pivot / Fibonacci seviyeleri, Stochastic, ADX, OBV
- Hisse tarayıcı (F/K, PD/DD, ROE, temettü verimi, sektör, katılım)

**Piyasa verisi**
- Dolar, euro, gram altın — 15 dakikada bir, yerli kaynaktan
- 9 Türkçe kaynaktan piyasa haber akışı
- KAP bildirimleri, önemli pay sahibi hareketleri, içeriden öğrenen işlemleri
- **Temettü takvimi** — yaklaşan nakit ödemeler, tutar ve brüt verimle
- **Halka arz takvimi** — fiyat, talep toplama tarihleri, dağıtım yöntemi
- TEFAS katılım fonları (390 fon)

**Portföy**
- Performans karnesi: isabet oranı, ortalama tutma süresi
- Risk paneli, XU100 kıyası, karşı-olgusal analiz ("ya hiç almasaydım")
- Temettü geliri projeksiyonu, katılım uyum karnesi
- Bekleyen limit emirleri, kişisel işlem botu

**Diğer**
- Web push bildirimleri (fiyat alarmı, temettü, KAP), PWA
- Favori listesi, hisse karşılaştırma, ısı haritası, topluluk yorumları

## Teknoloji

FastAPI · SQLAlchemy 2 · PostgreSQL · Next.js 16 · TailwindCSS 4 · APScheduler

Tek VPS üzerinde iki pm2 süreci; konteyner yok, mesaj kuyruğu yok.
Uygulama **kullanıcı isteği sırasında hiçbir dış servise bağlanmaz** — tüm
dış çağrılar zamanlanmış işlerde yapılır, uçlar yalnızca veritabanından okur.

## Veri sağlığı

`GET /api/health` dokuz veri hattının satır sayısını ve tazeliğini raporlar.

Bu uç, "kod patlamıyor ama veri sessizce gelmiyor" sınıfı arızalar için var —
bunlar hata logu üretmez, 200 dönen boş yanıtlardır ve elle kazmadan fark
edilmezler. Her hattın tazelik eşiği, onu besleyen işin çalışma sıklığından
türetilmiştir.

## Test

```bash
cd backend
python -m uvicorn main:app --port 4000     # ayrı terminalde
python smoke_test.py                       # 101 test
```

Her push'ta GitHub Actions **Python 3.9 ve 3.12** üzerinde duman testini
koşar ve ön yüzü derler. Testler tamamen yerel bir örneğe gider: CI'ın işi
"kod bozuldu mu" sorusunu yanıtlamak, "dış servis şu an ayakta mı" sorusunu
değil.

## Kurulum

```bash
# Backend
cd backend && python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe -m uvicorn main:app --reload --port 4000

# Frontend
cd frontend && npm install && npm run dev
```

`DATABASE_URL` tanımlı değilse yerelde SQLite kullanılır.
`DISABLE_SCHEDULER=1` zamanlanmış işleri kapatır (test ve CI için).

---

> Yatırım tavsiyesi değildir. Gerçek para kullanılmaz, veriler gecikmelidir.
>
> Design by Eyüphan İpek
