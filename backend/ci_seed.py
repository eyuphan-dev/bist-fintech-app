"""
ci_seed.py
----------
CI için deterministik test verisi üretir. ÜRETİMDE ÇALIŞTIRILMAZ.

NEDEN GEREKLİ
-------------
CI'da veritabanı boştur: `init_db` 165 hisseyi tohumlar ama fiyat, günlük bar,
temettü ve haber verisi yoktur. Ölçüldü — boş veritabanında duman testinin 95
testinden 17'si "veri yok" durumuna düşüyor ve bir tanesi doğrudan
başarısız oluyordu (`/api/stocks/THYAO` fiyat verisi olmadığı için HTTP 400).

Yani veri olmadan CI, uçların çoğunu SADECE BOŞ YOLDAN geçiriyor: fiyat
hesabı, yüzde değişim, pivot, grafik, portföy değerlemesi ve backtest gibi
asıl mantık hiç çalışmıyor. Bu haliyle CI "uygulama açılıyor mu" testinden
ibaret kalırdı.

NE ÜRETİLİR
-----------
Az sayıda hisse için (varsayılan 8) sentetik ama TUTARLI veri:
  • 120 iş günü günlük OHLCV barı — pivot, grafik, mevsimsellik, backtest
  • son fiyat tikleri — portföy değerlemesi, % değişim
  • birkaç temettü kaydı — temettü paneli ve projeksiyon

ÜRETİLEN VERİ GERÇEKÇİ OLMAK ZORUNDA DEĞİL, TUTARLI OLMAK ZORUNDA:
high >= max(open, close), low <= min(open, close), fiyatlar pozitif. Testin
ölçtüğü şey sayıların doğruluğu değil, kod yollarının çalışması.

Rastgelelik SABİT TOHUMLUDUR (random.seed): aynı commit her koşuda aynı
veriyi üretir. Aksi hâlde CI kırmızı/yeşil arasında salınır ve güveni yok
eder — testin kendisi kararsız olursa hiçbir bulgusuna inanılmaz.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

import models

# Sabit tohum — aynı commit her koşuda aynı veriyi üretir.
TOHUM = 20260828

# Kaç hisseye veri üretilecek. Hepsine üretmek CI'ı yavaşlatır; duman testi
# THYAO ve ASELS'e bakıyor, gerisi çeşitlilik için.
VARSAYILAN_HISSELER = ("THYAO", "ASELS", "GARAN", "BIMAS", "EREGL", "SISE", "TUPRS", "SARKY")

# Kaç iş günü geriye veri üretilecek. 120 gün; 20 günlük pivot penceresi,
# 50/200 günlük ortalamalar ve backtest için yeterli.
GUN_SAYISI = 120


def _is_gunleri(bitis: date, adet: int) -> List[date]:
    """Bitiş tarihinden geriye doğru `adet` iş günü (hafta sonu atlanır)."""
    gunler: List[date] = []
    gun = bitis
    while len(gunler) < adet:
        if gun.weekday() < 5:  # 0-4 = Pazartesi-Cuma
            gunler.append(gun)
        gun -= timedelta(days=1)
    return sorted(gunler)


def seed(db: Session, semboller=VARSAYILAN_HISSELER, gun_sayisi: int = GUN_SAYISI) -> dict:
    """Test verisini yazar; zaten veri varsa hiçbir şey yapmaz (idempotent)."""
    rnd = random.Random(TOHUM)

    if db.query(models.StockPriceDaily).count() > 0:
        print("[CI-Seed] Günlük bar verisi zaten var, tohumlama atlandı.")
        return {"hisse": 0, "bar": 0, "tik": 0, "temettu": 0}

    # Pivot ve "önceki kapanış" hesapları BUGÜNDEN ÖNCEKİ günlere bakar, bu
    # yüzden seri dünde biter. Bugüne kadar üretilirse pivot penceresi bir
    # gün kayar ve testler ortamın saatine göre farklı davranır.
    bitis = date.today() - timedelta(days=1)
    gunler = _is_gunleri(bitis, gun_sayisi)

    sayac = {"hisse": 0, "bar": 0, "tik": 0, "temettu": 0}

    for sembol in semboller:
        stock = db.query(models.Stock).filter_by(symbol=sembol).first()
        if not stock:
            continue
        sayac["hisse"] += 1

        fiyat = rnd.uniform(20.0, 400.0)
        son_kapanis = fiyat

        for gun in gunler:
            # Rastgele yürüyüş; %3'lük günlük bant gerçekçi bir aralık.
            degisim = rnd.uniform(-0.03, 0.03)
            acilis = son_kapanis
            kapanis = max(1.0, acilis * (1 + degisim))
            # TUTARLILIK ŞARTI: high >= max(open, close), low <= min(open, close).
            # Bu bozulursa pivot ve Fibonacci hesapları anlamsız sayı üretir.
            yuksek = max(acilis, kapanis) * rnd.uniform(1.000, 1.015)
            dusuk = min(acilis, kapanis) * rnd.uniform(0.985, 1.000)

            db.add(models.StockPriceDaily(
                stock_id=stock.id,
                trade_date=gun,
                open=round(acilis, 2),
                high=round(yuksek, 2),
                low=round(dusuk, 2),
                close=round(kapanis, 2),
                volume=rnd.randint(100_000, 10_000_000),
            ))
            sayac["bar"] += 1
            son_kapanis = kapanis

        # Yahoo'nun resmi referansı olarak son kapanışı yaz — % değişim
        # hesabının birinci öncelikli kaynağı burası (bkz. _bulk_price_and_change).
        stock.previous_close = round(son_kapanis, 2)

        # Son fiyat tikleri. Tik "taze" olmalı: _get_latest_db_price 7 günden
        # eski tiki yok sayıp günlük kapanışa düşer.
        simdi = datetime.utcnow()
        for i in range(3):
            db.add(models.StockPrice(
                stock_id=stock.id,
                price=round(son_kapanis * rnd.uniform(0.995, 1.005), 2),
                volume=rnd.randint(1000, 100_000),
                recorded_at=simdi - timedelta(minutes=5 * i),
            ))
            sayac["tik"] += 1

        # Birkaç yıllık temettü — temettü paneli ve istikrar sınıflandırması
        # için en az birkaç yıl gerekiyor.
        for yil_geri in range(1, 5):
            odeme = date(bitis.year - yil_geri, 5, 15)
            db.add(models.DividendHistory(
                stock_id=stock.id,
                pay_date=odeme,
                amount=round(son_kapanis * rnd.uniform(0.01, 0.04), 4),
            ))
            sayac["temettu"] += 1

    db.commit()
    print("[CI-Seed] {hisse} hisse, {bar} günlük bar, {tik} tik, {temettu} temettü yazıldı.".format(**sayac))
    return sayac


if __name__ == "__main__":
    from database import SessionLocal

    seed(SessionLocal())
