# BIST Sanal Borsa Simülatörü

Borsa İstanbul hisseleri için **gerçek para kullanılmayan** bir yatırım
simülatörü. Sanal bakiyeyle başlarsınız, gerçek fiyatlarla alım-satım
yaparsınız.

**https://borsa-trader.duckdns.org**

Odağı **katılım (faizsiz) finans**. Uygunluk bilgisi tahmin değil, şirketlerin
KAP'a bildirdiği resmî beyandan okunur ve kaynağıyla birlikte gösterilir.

Analiz araçları, temettü ve halka arz takvimi, KAP bildirimleri, Türkçe piyasa
haberleri, portföy risk ve performans panelleri, işlem botu ve push bildirimi
içerir.

## Teknoloji

FastAPI · SQLAlchemy · PostgreSQL · Next.js 16 · TailwindCSS · APScheduler

## Kurulum

```bash
# Backend
cd backend
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe -m uvicorn main:app --reload --port 4000

# Frontend
cd frontend
npm install
npm run dev
```

`DATABASE_URL` tanımlı değilse yerelde SQLite kullanılır.
`DISABLE_SCHEDULER=1` zamanlanmış işleri kapatır.

## Test

```bash
cd backend && python smoke_test.py
```

Backend'in ayakta olması gerekir. Her push'ta GitHub Actions aynı testi
Python 3.9 ve 3.12 üzerinde koşar ve ön yüzü derler.

---

> Yatırım tavsiyesi değildir. Gerçek para kullanılmaz, veriler gecikmelidir.
>
> Design by Eyüphan İpek
