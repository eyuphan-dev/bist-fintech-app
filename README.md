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

## Sunucu Notu: Deploy sonrası eski arayüz görünüyorsa

aaPanel, `/www/server/nginx/conf/proxy.conf` içinde **global** bir
`proxy_cache cache_one;` (inactive=1d) tanımlar ve tüm vhost'lar bunu miras alır.
Bu açıkken deploy sonrası nginx, eski HTML ve JS chunk'larını 1 güne kadar
servis etmeye devam eder — tarayıcı cache'i temizlense bile.

`/www/server/panel/vhost/nginx/borsa-trader.conf` içindeki her `proxy_pass`
satırının altında `proxy_cache off;` bulunmalıdır. Bu dosya git'te değildir;
aaPanel'de site yeniden oluşturulursa ayar kaybolur.

Teşhis (silinmiş bir chunk hâlâ 200 dönüyorsa önbellek var demektir):

```bash
curl -s http://127.0.0.1:3001/<sayfa>            # Next ne diyor?
curl -s https://borsa-trader.duckdns.org/<sayfa> # nginx ne diyor?
# Farklıysa:
grep -c "proxy_cache off" /www/server/panel/vhost/nginx/borsa-trader.conf
find /www/server/nginx/proxy_cache_dir -type f -delete
/www/server/nginx/sbin/nginx -s reload
```

Not: `/api/` yanıtları FastAPI cache başlığı göndermediği için önbelleğe
girmiyor (denetlendi). Ancak varsayılan `proxy_cache_key` `Authorization`
başlığını içermez — API'ye cache başlığı eklenirse kullanıcılar arası veri
sızıntısı riski doğar.
