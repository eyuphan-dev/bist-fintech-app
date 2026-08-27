"""
temettu_takvimi.py
------------------
KAP "Hak Kullanımı" bildirimlerinden YAKLAŞAN temettü ödemelerini çıkarır.

NEDEN
-----
Uygulamada temettü merkezî bir kavram (katılım finansı odaklı) ama yalnızca
GEÇMİŞ ödemeler vardı (`dividend_history`). Kullanıcı "hangi hisse ne zaman,
ne kadar temettü ödeyecek" sorusunun cevabını hiçbir yerde göremiyordu.

KAP bunu "Hak Kullanımı" kategorisinde yapısal bir tabloyla yayımlıyor:

    KIYMET TÜRÜ | ISIN | BORSA KODU | İŞLEM TİPİ | TEMETTÜ NET ORAN % |
    TEMETTÜ BRÜT ORAN | NAKİT ÖDEME TARİHİ | PARA BİRİMİ

ORANIN ANLAMI ÖLÇÜLEREK ÇÖZÜLDÜ
-------------------------------
"Oran" alanının TL mi yüzde mi olduğu belgede yazmıyor. İki bağımsız kontrolle
doğrulandı:

  1. AHGAZ bildiriminde brüt 5,76923 ve net 4,90384 yazıyor.
     5,76923 x 0,85 = 4,90385  ->  aradaki fark tam olarak %15 stopaj.
     Demek ki ikisi de AYNI BİRİMDE ve oran cinsinden.

  2. Kendi `dividend_history` tablomuzda AHGAZ'ın 2024 ödemesi 0,019231 TL,
     TURSG'nin 2025 ödemesi 0,100000 TL. Bunlar sırasıyla %1,9231 ve %10
     oranlarına karşılık geliyor.

  3. EN GÜÇLÜ DOĞRULAMA — BEGYO: KAP bildirimindeki %3,06748 oranından
     hesaplanan 0,030675 TL, `dividend_history`deki gerçekleşmiş ödeme
     tutarıyla BİREBİR AYNI çıktı. Yani dönüşüm bağımsız bir kaynakla
     tam olarak doğrulandı.

Sonuç: oran, 1 TL NOMİNAL paya göre yüzdedir.
    pay başına brüt TL = brüt oran / 100

Bu bölme uydurma değil, iki ayrı kaynakla doğrulanmış bir dönüşümdür. Yine de
hem ORAN hem HESAPLANAN TL saklanır; kullanıcı hangisine bakacağını seçebilir
ve kaynak KAP bildirimi her kayıtta bağlantılıdır.

SADECE NAKİT TEMETTÜ ALINIR
---------------------------
"Hak Kullanımı" kategorisi bedelsiz sermaye artırımı, rüçhan hakkı ve
ortaklıktan çıkarma gibi işlemleri de içerir. Bunlar temettü değildir ve
temettü takvimine karışırlarsa kullanıcıyı yanıltır; `İŞLEM TİPİ` alanı
"Nakit Temettü" içermeyen satırlar elenir.
"""

from __future__ import annotations

import html
import re
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

import models
from text_utils import tr_fold

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

KAP_BILDIRIM_URL = "https://www.kap.org.tr/tr/Bildirim/{index}"

# Bu başlıklar "Hak Kullanımı" kategorisine girer; temettü tablosu bunlarda bulunur.
BASLIK_ISARETLERI = ("hak kullanimi", "hak kullanim islemleri")

# İŞLEM TİPİ alanında aranan ifade. Bedelsiz artırım / rüçhan bunu içermez.
NAKIT_TEMETTU_ISARETI = "nakit temettu"

# Stopaj oranı yalnızca DOĞRULAMA için kullanılır (net ~= brüt * 0.85).
# Hesaplama için kullanılmaz; net değer KAP'tan olduğu gibi alınır.
BEKLENEN_STOPAJ = 0.15


def _duz(parca: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", parca)).split())


def tr_oran(ham: str) -> Optional[float]:
    """
    '5,76923' -> 5.76923 ,  '1.234,50' -> 1234.5

    Nokta BİNLİK ayracıdır (aynı tuzak tr_market, katilim_kap ve ipo_client'ta
    da belgeli): float('1.234') patlamaz, 1.234 döndürür.
    """
    if not ham:
        return None
    metin = ham.strip()
    if not re.search(r"\d", metin):
        return None
    metin = metin.replace(".", "").replace(",", ".")
    try:
        deger = float(metin)
    except ValueError:
        return None
    return deger if deger >= 0 else None


def tr_tarih(ham: str) -> Optional[date]:
    """'26/08/2026' ya da '26.08.2026' -> date(2026, 8, 26)."""
    if not ham:
        return None
    eslesme = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", ham)
    if not eslesme:
        return None
    gun, ay, yil = (int(x) for x in eslesme.groups())
    try:
        return date(yil, ay, gun)
    except ValueError:
        return None


def tablo_ayristir(hamsayfa: str) -> List[Dict[str, Any]]:
    """
    Bildirim sayfasındaki hak kullanım tablosunu satır satır çözer.

    Eşleştirme BAŞLIK HÜCRELERİNİN SIRASINA göre yapılır, sabit sütun
    indeksine göre değil: KAP kolon sırasını değiştirirse sabit indeks sessizce
    yanlış alanı okur (tarih yerine oran gibi), başlık eşleştirmesi ise
    okuyamayıp None döner. Sessiz yanlış veriden gürültülü boşluk iyidir.
    """
    satirlar = re.findall(r"<tr[^>]*>(.*?)</tr>", hamsayfa, re.S)
    basliklar: Optional[List[str]] = None
    kayitlar: List[Dict[str, Any]] = []

    for satir in satirlar:
        # BOŞ HÜCRELER ELENMEZ. Elenirse başlık–veri hizası bozulur: bu tabloda
        # "ORTAKLIKTAN ÇIKARMA NAKİT ÖDEME ORAN" ve son "AÇIKLAMA" sütunları
        # nakit temettü satırlarında boştur, dolayısıyla filtreleme ödeme
        # tarihini bir sütun kaydırıyor ve tarih yerine para birimi okunuyordu
        # (ölçüldü: AHGAZ satırında tarih None çıktı, oranlar doğruydu).
        hucreler = [_duz(h) for h in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", satir, re.S)]
        if len([h for h in hucreler if h]) < 5:
            continue

        katlanmis = [tr_fold(h) for h in hucreler]

        # Başlık satırı: "borsa kodu" ve "islem tipi" birlikte geçiyorsa.
        if any("borsa kodu" in k for k in katlanmis) and any("islem tipi" in k for k in katlanmis):
            basliklar = katlanmis
            continue

        # Hiza korunduğu için sütun sayıları eşleşmeli; eşleşmiyorsa bu satır
        # bu tabloya ait değildir (iç içe tablo, alt başlık vb.).
        if not basliklar or len(hucreler) < len(basliklar):
            continue

        def al(*anahtarlar: str) -> Optional[str]:
            for i, b in enumerate(basliklar or []):
                if any(a in b for a in anahtarlar) and i < len(hucreler):
                    return hucreler[i]
            return None

        islem_tipi = al("islem tipi") or ""
        if NAKIT_TEMETTU_ISARETI not in tr_fold(islem_tipi):
            continue

        kayitlar.append({
            "symbol": (al("borsa kodu") or "").strip().upper() or None,
            "islem_tipi": islem_tipi,
            "net_oran": tr_oran(al("net oran") or ""),
            "brut_oran": tr_oran(al("brut oran") or ""),
            "odeme_tarihi": tr_tarih(al("odeme tarihi") or ""),
            "para_birimi": (al("para birimi") or "TRY").strip() or "TRY",
        })

    return kayitlar


def bildirimi_cek(index: int, timeout: int = 25) -> List[Dict[str, Any]]:
    try:
        yanit = requests.get(KAP_BILDIRIM_URL.format(index=index), headers=HEADERS, timeout=timeout)
        yanit.raise_for_status()
    except Exception as e:
        print(f"[Temettü] {index} indirilemedi: {e}")
        return []
    return tablo_ayristir(yanit.text)


def _index_coz(kap_url: Optional[str]) -> Optional[int]:
    if not kap_url:
        return None
    m = re.search(r"/Bildirim/(\d+)", kap_url)
    return int(m.group(1)) if m else None


def temettu_takvimini_senkronize_et(db: Session, geriye_gun: int = 60,
                                    gecikme_sn: float = 0.6) -> Dict[str, int]:
    """
    Son `geriye_gun` gündeki "Hak Kullanımı" bildirimlerini gezip nakit temettü
    ödemelerini `dividend_events` tablosuna yazar.

    GERİYE BAKMA NEDENİ: bildirim ödemeden ÖNCE yayımlanır ama biz KAP akışını
    günde bir çekiyoruz; geniş bir pencere, kaçırılan bildirimi bir sonraki
    turda yakalamayı sağlar. Tekilleştirme (symbol, ödeme tarihi) ile yapılır.
    """
    esik = datetime.utcnow() - timedelta(days=geriye_gun)
    bildirimler = (
        db.query(models.KapNotification)
        .filter(models.KapNotification.publish_date >= esik,
                models.KapNotification.kap_url.isnot(None))
        .order_by(models.KapNotification.publish_date.desc())
        .all()
    )

    # Aynı bildirim birden çok hisse için tekrar kaydedilmiş olabiliyor;
    # her bildirimi BİR KEZ indir.
    indexler: Dict[int, models.KapNotification] = {}
    for b in bildirimler:
        if not any(isaret in tr_fold(b.title or "") for isaret in BASLIK_ISARETLERI):
            continue
        idx = _index_coz(b.kap_url)
        if idx and idx not in indexler:
            indexler[idx] = b

    hisse_id = {s.symbol: s.id for s in db.query(models.Stock).all()}
    sayac = {"bildirim": len(indexler), "satir": 0, "yeni": 0, "guncellenen": 0, "atlanan": 0}

    for idx, bildirim in indexler.items():
        for kayit in bildirimi_cek(idx):
            sayac["satir"] += 1
            sembol = kayit["symbol"]
            odeme = kayit["odeme_tarihi"]
            if not sembol or not odeme or sembol not in hisse_id:
                sayac["atlanan"] += 1
                continue

            brut_oran = kayit["brut_oran"]
            # Pay başına brüt TL = oran / 100 (bkz. modül başlığındaki doğrulama).
            brut_tl = round(brut_oran / 100.0, 6) if brut_oran is not None else None

            mevcut = (
                db.query(models.DividendEvent)
                .filter_by(symbol=sembol, payment_date=odeme)
                .first()
            )
            if mevcut is None:
                mevcut = models.DividendEvent(symbol=sembol, payment_date=odeme)
                db.add(mevcut)
                sayac["yeni"] += 1
            else:
                sayac["guncellenen"] += 1

            mevcut.stock_id = hisse_id[sembol]
            mevcut.event_type = kayit["islem_tipi"][:60]
            mevcut.gross_rate_pct = brut_oran
            mevcut.net_rate_pct = kayit["net_oran"]
            mevcut.gross_amount_per_share = brut_tl
            mevcut.currency = kayit["para_birimi"][:8]
            mevcut.source_url = bildirim.kap_url
            mevcut.updated_at = datetime.utcnow()

        if gecikme_sn:
            time.sleep(gecikme_sn)

    db.commit()
    print(f"[Temettü] {sayac['bildirim']} bildirim tarandı, {sayac['satir']} satır, "
          f"{sayac['yeni']} yeni, {sayac['guncellenen']} güncellendi, {sayac['atlanan']} atlandı.")
    return sayac
