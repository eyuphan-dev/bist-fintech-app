# BİST Fintech App

Sanal (paper trading) borsa simülasyonu — BİST hisseleri üzerinde gerçek zamanlı
fiyat takibi, portföy yönetimi, kişisel AI trading botu ve daha fazlası.

## Teknoloji

- **Backend**: FastAPI (Python), PostgreSQL, APScheduler (fiyat güncelleme/bot döngüsü)
- **Frontend**: Next.js (React, TypeScript, Tailwind)
- **Prod barındırma**: Kendi sunucumuz (VPS), pm2 ile process yönetimi, Nginx + Let's Encrypt SSL

Prod deploy/güncelleme adımları için **`eyup.md`** dosyasına bakın (git'e dahil değil, yalnızca yerelde).

## Yerelde Çalıştırma (Geliştirme)

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows
# source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
cp .env.example .env           # JWT_SECRET_KEY, FRONTEND_URL vs. doldurun
uvicorn main:app --reload --port 8000
```

`DATABASE_URL` tanımlı değilse otomatik olarak yerel bir SQLite dosyasına
(`backend/bist_app.db`) düşer — hızlı geliştirme için yeterlidir.

### Frontend

```bash
cd frontend
npm install
npm run dev          # varsayılan port 3000
```

`frontend/.env.local` içinde `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api` olmalı.

## Proje Yapısı

```
backend/
  main.py       — API endpoint'leri
  bot.py        — Kişisel AI Trader strateji motoru + oturum yönetimi
  auth.py       — JWT kimlik doğrulama
  models.py     — SQLAlchemy modelleri
  schemas.py    — Pydantic response şemaları
  scheduler.py  — APScheduler işleri (fiyat güncelleme, bot döngüsü)
frontend/
  src/app/      — Next.js App Router sayfaları ve bileşenleri
```
