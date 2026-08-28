#!/bin/bash
# Uretimde backend'i baslatan betik. pm2 bunu "borsa-backend" olarak calistirir:
#   pm2 start /opt/borsa/backend/start.sh --name borsa-backend --interpreter bash
#
# NEDEN AYRI BIR BETIK: pm2 dogrudan uvicorn'u calistirsaydi .env yuklenmezdi
# ve uygulama DATABASE_URL'i goremeyip SQLite'a duserdi -- yani uretim
# veritabani yerine bos bir yerel dosyayla acilirdi. `set -a` ile source
# etmek, dosyadaki her degiskeni cocuk surece aktarir.
#
# NEDEN TEK ISCI (--workers 1): sinyal onbellegi surec ici bir Python
# sozlugu. Cok isciye cikilirsa her iscinin ayri onbellegi olur ve ayni
# istek farkli sonuc dondurur. Olceklemeden once onbellek disari tasinmali.

cd /opt/borsa/backend
set -a
source .env
set +a
exec ./venv/bin/uvicorn main:app --host 0.0.0.0 --port 4000 --workers 1
