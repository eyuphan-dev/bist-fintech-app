"""
tr_market.py — Döviz ve altının ANLIK kurları, yurt içi kaynaktan.

NEDEN AYRI BİR MODÜL
--------------------
Bu veriler bilerek yfinance'ın dışına alındı. İki ayrı sorun vardı:

1) GRAM ALTIN YANLIŞTI. yfinance'ta gram altın diye bir sembol yok; eskiden
   ons altın × dolar kuru ile türetiliyordu (bkz. daily_history.py, artık
   devre dışı). Ons için `GC=F` kullanılıyordu ve `GC=F` COMEX VADELİ
   sözleşmesidir, spot değil. Vadeli spotun üzerinde işlem görür. Ölçüldü:

       spot ons      4641,83 USD
       GC=F vadeli   4695,60 USD      -> contango %1,16
       gram altın    7175,52 TL       (spot paritesi)
       gösterdiğimiz 7251,81 TL       -> 76 TL fazla

   Bu sistematik bir sapmaydı, gürültü değil.

2) GÜNDE BİR KEZ TAZELENİYORDU (TR 11:00). Döviz ve altın neredeyse 24 saat
   işlem görüyor; sayı sabah donup ertesi sabaha kadar öyle kalıyordu.

KAYNAK SEÇİMİ
-------------
Birincil: finans.truncgil.com — anahtar istemiyor, yurt içi, ~15 dakikada bir
güncelleniyor, gram altını hazır veriyor. Frankfurt'taki sunucudan proxy'siz
erişiliyor (ölçüldü: 116 ms). BİST'in aksine IP engeli yok.

Doğrulandı: kaynağın gram altını, kendi ons ve dolar değerlerinin paritesine
kuruşu kuruşuna eşit (7175,52 = 4641,83 × 48,0810 ÷ 31,1034768). Yani kara
kutu değil, içi tutarlı.

Yedek: TCMB (www.tcmb.gov.tr/kurlar/today.xml) — resmî, devlet kaynağı, ama
YALNIZCA DÖVİZ var ve günde tek bültendir (hafta içi ~15:30, hafta sonu yok).
Bu yüzden birincil olamaz; sadece truncgil düşerse dövizin tamamen boş
kalmaması için var. Altının yedeği yok — kaynak düşerse gram altın eski
değerinde kalır, ki uydurulmuş bir sayı göstermekten iyidir.
"""
from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Optional

TRUNCGIL_URL = "https://finans.truncgil.com/today.json"
TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
ZAMAN_ASIMI = 12

# Bazı sunucular başlıksız isteği reddediyor; kimliğimizi açıkça belirtiyoruz.
_BASLIK = {"User-Agent": "borsa-trader/1.0 (+https://borsa-trader.duckdns.org)"}


def _getir(url: str) -> bytes:
    istek = urllib.request.Request(url, headers=_BASLIK)
    with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as yanit:
        return yanit.read()


def tr_sayi(metin: str) -> Optional[float]:
    """
    '7.175,10' -> 7175.10 ,  '$4.641,56' -> 4641.56

    Türk biçiminde nokta BİNLİK ayracıdır. float('7.175,10') doğrudan patlar,
    ama daha sinsisi float('7.175') = 7.175 sessizce BİN KAT KÜÇÜK bir sayı
    döndürürdü. Bu yüzden ayrıştırma elle yapılıyor.
    """
    if metin is None:
        return None
    t = str(metin).strip().replace("$", "").replace("₺", "").replace("%", "").replace(" ", "")
    if not t:
        return None
    t = t.replace(".", "").replace(",", ".")
    try:
        d = float(t)
    except ValueError:
        return None
    return d if d > 0 else None


def _orta(kayit: dict) -> Optional[float]:
    """Alış/satış ortası. Tek taraf eksikse var olanı döndürür."""
    a = tr_sayi(kayit.get("Alış"))
    s = tr_sayi(kayit.get("Satış"))
    if a and s:
        return (a + s) / 2
    return a or s


def _degisim(kayit: dict) -> Optional[float]:
    """
    Kaynağın kendi günlük değişimi ('%0,96' -> 0.96, '%-0,02' -> -0.02).

    Bunu kendimiz hesaplamak yerine kaynaktan almanın sebebi: kendi
    geçmişimizdeki dünkü kapanış başka bir kaynaktan gelmiş olabilir ve iki
    kaynağı karıştırmak, aslında olmayan bir günlük değişim üretir.
    tr_sayi eksi işaretini yiyor, o yüzden burada elle ele alınıyor.
    """
    ham = kayit.get("Değişim")
    if ham is None:
        return None
    metin = str(ham).strip()
    eksi = metin.lstrip("%").strip().startswith("-")
    d = tr_sayi(metin.replace("-", ""))
    if d is None:
        return None
    return -d if eksi else d


def _truncgil() -> Dict[str, dict]:
    veri = json.loads(_getir(TRUNCGIL_URL).decode("utf-8"))

    guncelleme = None
    try:
        guncelleme = datetime.strptime(veri.get("Update_Date", ""), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        pass

    esleme = {"USDTRY": "USD", "EURTRY": "EUR", "GRAMALTIN": "gram-altin"}
    sonuc: Dict[str, dict] = {}
    for bizim, onunki in esleme.items():
        kayit = veri.get(onunki)
        if not isinstance(kayit, dict):
            continue
        fiyat = _orta(kayit)
        if fiyat is None:
            continue
        sonuc[bizim] = {
            "price": fiyat,
            "change_1d_pct": _degisim(kayit),
            "source": "truncgil",
            "as_of": guncelleme or datetime.utcnow(),
        }
    return sonuc


def _tcmb() -> Dict[str, dict]:
    """Yalnızca döviz. TCMB bülteni altın içermez."""
    kok = ET.fromstring(_getir(TCMB_URL))

    tarih = None
    try:
        tarih = datetime.strptime(kok.attrib.get("Tarih", ""), "%d.%m.%Y")
    except (ValueError, TypeError):
        pass

    sonuc: Dict[str, dict] = {}
    for kod, bizim in (("USD", "USDTRY"), ("EUR", "EURTRY")):
        dugum = kok.find(f".//Currency[@Kod='{kod}']")
        if dugum is None:
            continue
        alis = dugum.findtext("ForexBuying")
        satis = dugum.findtext("ForexSelling")
        try:
            degerler = [float(x) for x in (alis, satis) if x and float(x) > 0]
        except (TypeError, ValueError):
            degerler = []
        if not degerler:
            continue
        sonuc[bizim] = {
            "price": sum(degerler) / len(degerler),
            "change_1d_pct": None,      # TCMB bülteni değişim vermez
            "source": "tcmb",
            "as_of": tarih or datetime.utcnow(),
        }
    return sonuc


def fetch_tr_quotes() -> Dict[str, dict]:
    """
    {'USDTRY': {'price', 'change_1d_pct', 'source', 'as_of'}, ...}

    Kaynaklardan hiçbiri cevap vermezse BOŞ SÖZLÜK döner. Çağıran taraf bunu
    "yazacak bir şey yok" diye ele almalı; eldeki değeri sıfırlamamalıdır.
    Bayat bir kur, sıfır bir kurdan iyidir.
    """
    sonuc: Dict[str, dict] = {}
    try:
        sonuc.update(_truncgil())
    except Exception as e:
        print(f"[TRMarket] truncgil alinamadi: {e}")

    # Yedek YALNIZCA birincil kaynağın veremediği semboller için devreye girer;
    # dolu bir değerin üzerine yazmaz.
    if "USDTRY" not in sonuc or "EURTRY" not in sonuc:
        try:
            for anahtar, deger in _tcmb().items():
                sonuc.setdefault(anahtar, deger)
        except Exception as e:
            print(f"[TRMarket] tcmb alinamadi: {e}")

    return sonuc


# ---------------------------------------------------------------------------
# Kalıcılaştırma
# ---------------------------------------------------------------------------
def store_tr_quotes(db) -> int:
    """
    Anlık kurları index_history'e yazar. Aynı günün satırı ÜZERİNE yazılır.

    Neden aynı satırın üzerine: index_history (symbol, trade_date) üzerinde
    tekil; gün içinde her tazeleme "bugünün en son değeri"ni günceller, dünkü
    satır ise kesinleşmiş olarak yerinde kalır. Böylece 1 günlük ve 30 günlük
    değişim hesapları bozulmadan çalışmaya devam eder.
    """
    import models

    kotasyonlar = fetch_tr_quotes()
    if not kotasyonlar:
        # Hiçbir kaynak cevap vermedi. Elimizdekine DOKUNMUYORUZ.
        print("[TRMarket] hicbir kaynak cevap vermedi, mevcut degerler korundu.")
        return 0

    simdi = datetime.utcnow()
    yazilan = 0
    for sembol, veri in kotasyonlar.items():
        gun = veri["as_of"].date()
        satir = (
            db.query(models.IndexHistory)
            .filter_by(symbol=sembol, trade_date=gun)
            .one_or_none()
        )
        if satir is None:
            satir = models.IndexHistory(symbol=sembol, trade_date=gun)
            db.add(satir)
        satir.close = round(veri["price"], 2)
        satir.updated_at = simdi
        satir.source = veri["source"]
        satir.change_1d_pct = veri["change_1d_pct"]
        yazilan += 1

    db.commit()
    ozet = ", ".join(f"{k}={v['price']:.2f}" for k, v in sorted(kotasyonlar.items()))
    print(f"[TRMarket] {yazilan} kotasyon guncellendi ({ozet})")
    return yazilan


def store_index_intraday(db) -> int:
    """
    BIST 100'ün gün içi değeri.

    Bu ayrı duruyor çünkü kaynağı farklı (yfinance, proxy üzerinden) ve yalnızca
    seans saatlerinde anlamlı. Eskiden XU100 de günde bir kez, TR 11:00'de
    yazılıyordu; BİST 18:00'de kapandığı için kaydedilen "kapanış" aslında
    yarım günlük bir ara değerdi ve günlük yüzde bunun üzerinden hesaplanıyordu.
    Ölçüldü: site %+0,54 gösterirken gerçek değişim %+0,28 idi.
    """
    import models
    from yf_retry import call_with_retry

    try:
        import yfinance as yf
        fiyat = call_with_retry(
            lambda: yf.Ticker("XU100.IS").fast_info["lastPrice"],
            attempts=2, label="XU100.fast_info",
        )
    except Exception as e:
        print(f"[TRMarket] XU100 alinamadi: {e}")
        return 0

    if not fiyat or float(fiyat) <= 0:
        return 0

    gun = datetime.utcnow().date()
    satir = (
        db.query(models.IndexHistory)
        .filter_by(symbol="XU100", trade_date=gun)
        .one_or_none()
    )
    if satir is None:
        satir = models.IndexHistory(symbol="XU100", trade_date=gun)
        db.add(satir)
    satir.close = round(float(fiyat), 2)
    satir.updated_at = datetime.utcnow()
    satir.source = "yfinance"
    # XU100'ün günlük değişimi uçta bir önceki İŞLEM GÜNÜ satırından hesaplanır;
    # kaynak hazır bir değişim vermiyor.
    satir.change_1d_pct = None

    db.commit()
    print(f"[TRMarket] XU100 guncellendi: {float(fiyat):.2f}")
    return 1
