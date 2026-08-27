# BIST Sanal Borsa Simülatörü

Borsa İstanbul hisseleri için **gerçek para kullanılmayan** bir yatırım
simülatörü. Kullanıcı sanal bakiyeyle başlar, gerçek fiyatlarla alım-satım
yapar ve ücretli terminallerde para karşılığı sunulan analiz araçlarına
ücretsiz erişir.

**https://borsa-trader.duckdns.org**

## Öne çıkanlar

- Katılım (faizsiz) uygunluk taraması
- Strateji backtest'i ve DCA simülasyonu
- Piotroski F-Skoru, analist konsensüsü, finansal tablolar
- Performans karnesi — isabet oranı ve ortalama tutma süresi
- KAP bildirimleri, içeriden öğrenen işlemleri, yabancı takas trendi
- Kişisel işlem botu, web push bildirimleri, PWA

## Teknoloji

FastAPI · SQLAlchemy · PostgreSQL · Next.js 16 · TailwindCSS · APScheduler

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

---

> Yatırım tavsiyesi değildir. Gerçek para kullanılmaz, veriler gecikmelidir.
>

