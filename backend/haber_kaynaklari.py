"""
haber_kaynaklari.py
-------------------
Türkçe finans/ekonomi RSS kaynaklarından haber çeker.

NEDEN
-----
Ölçüldü: Yahoo Finance'ın BİST haber kapsamı çok zayıf. Üretimde 165 hissenin
yalnızca 29'unda haber vardı, en yenisi 5 gün eskiydi; 136 hisse sayfası haber
bölümü boş açılıyordu.

18 aday kaynak canlı olarak denendi; 10'u kullanılıyor ve tek turda ~330 haber
veriyor. Elenenler:
  • Bigpara, Mynet, Patronlar Dünyası, Borsa Gündem — 404 / RSS'i kaldırmışlar.
  • Milliyet — RSS'inde <link> ETİKETİ HİÇ YOK, yalnızca sayısal
    <guid isPermaLink="false">. Yani habere giden bir adres vermiyor.
    Tıklanamayan haber kartı göstermek yerine kaynak listeden çıkarıldı.

İKİ AYRI ÜRÜN
-------------
  1. GENEL PİYASA HABERLERİ — eşleştirme gerektirmez, olduğu gibi değerlidir.
     Kullanıcı "bugün piyasada ne oldu" sorusunun cevabını burada bulur.

  2. HİSSE HABERLERİ — haberin hangi şirkete ait olduğu metinden çıkarılır
     (bkz. haber_eslestirme.py). Ölçülen kesinlik %100, isabet düşük: 320
     haberin 7'si bir hisseyle eşleşiyor. Bu beklenen bir sonuçtur; ekonomi
     haberlerinin çoğu belirli bir hisseyle ilgili değildir.

TASARIM NOTU: neden kendi RSS ayrıştırıcımız var
------------------------------------------------
`feedparser` bağımlılığı eklemek yerine 30 satırlık regex ayrıştırma yeterli:
okuduğumuz alanlar yalnızca title/link/description/pubDate ve kaynakların
hepsi standart RSS 2.0 ya da Atom veriyor. Ek bağımlılık, tek sunucuda çalışan
bu uygulamada bakım yüküdür.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from sqlalchemy.orm import Session

import models
from haber_eslestirme import HaberEslestirici

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# (görünen ad, RSS adresi) — hepsi canlı olarak doğrulandı.
KAYNAKLAR = (
    ("Foreks", "https://www.foreks.com/rss"),
    ("TRT Haber", "https://www.trthaber.com/ekonomi_articles.rss"),
    ("Habertürk", "https://www.haberturk.com/rss/kategori/ekonomi.xml"),
    ("Anadolu Ajansı", "https://www.aa.com.tr/tr/rss/default?cat=ekonomi"),
    ("Dünya", "https://www.dunya.com/rss?dunya"),
    ("Ekonomim", "https://www.ekonomim.com/rss"),
    ("Bloomberg HT", "https://www.bloomberght.com/rss"),
    ("NTV", "https://www.ntv.com.tr/ekonomi.rss"),
    ("Investing", "https://tr.investing.com/rss/news_25.rss"),
    ("Sabah", "https://www.sabah.com.tr/rss/ekonomi.xml"),
)

# Kaç günden eski haber silinsin.
SAKLAMA_GUNU = 14


def _temizle(ham: Optional[str]) -> str:
    """CDATA sar(mal)ını, HTML varlıklarını ve etiketleri temizler."""
    if not ham:
        return ""
    metin = re.sub(r"<!\[CDATA\[|\]\]>", "", ham)
    metin = re.sub(r"<[^>]+>", " ", metin)
    metin = html.unescape(metin)
    return " ".join(metin.split())


def _alan(blok: str, etiket: str) -> str:
    m = re.search(r"<{0}[^>]*>(.*?)</{0}>".format(etiket), blok, re.S | re.I)
    return _temizle(m.group(1)) if m else ""


def _link(blok: str) -> str:
    """
    RSS <link>metin</link>, <link><![CDATA[...]]></link> ve Atom
    <link href="..."/> — üçü de desteklenir.

    CDATA TUZAĞI: ilk yazımda desen `<link[^>]*>([^<]+)</link>` idi ve
    `[^<]+` CDATA'nın açılışındaki "<" karakterinde hemen tıkanıyordu.
    Sonuç sessizdi — Bloomberg HT ve Milliyet'in 40 haberi URL'siz geldiği
    için tamamen eleniyordu (ölçüldü: 11 kaynaktan yalnızca 9'u akışta
    görünüyordu). Bu yüzden non-greedy `(.*?)` kullanılıyor.
    """
    m = re.search(r"<link[^>]*>(.*?)</link>", blok, re.S | re.I)
    if m and _temizle(m.group(1)):
        return _temizle(m.group(1))
    m = re.search(r'<link[^>]*href="([^"]+)"', blok, re.I)
    if m:
        return _temizle(m.group(1))
    # Son çare: guid çoğu kaynakta kalıcı bağlantıdır.
    m = re.search(r"<guid[^>]*>(.*?)</guid>", blok, re.S | re.I)
    aday = _temizle(m.group(1)) if m else ""
    return aday if aday.startswith("http") else ""


def kaynak_cek(ad: str, url: str, timeout: int = 20) -> List[Dict[str, str]]:
    """Tek bir RSS kaynağını çeker; hata durumunda boş liste döner."""
    try:
        yanit = requests.get(url, headers=HEADERS, timeout=timeout)
        yanit.raise_for_status()
        # Bazı kaynaklar charset'i yanlış bildiriyor; içerikten tahmin ettir.
        yanit.encoding = yanit.apparent_encoding or yanit.encoding or "utf-8"
    except Exception as e:
        print(f"[Haber] {ad} çekilemedi: {e}")
        return []

    haberler = []
    for blok in re.findall(r"<item\b.*?</item>|<entry\b.*?</entry>", yanit.text, re.S | re.I):
        baslik = _alan(blok, "title")
        if not baslik:
            continue
        haberler.append({
            "kaynak": ad,
            "baslik": baslik[:500],
            "ozet": (_alan(blok, "description") or _alan(blok, "summary"))[:1000],
            "url": _link(blok)[:500],
            "yayin": _alan(blok, "pubDate") or _alan(blok, "updated"),
        })
    return haberler


def tum_kaynaklari_cek() -> List[Dict[str, str]]:
    """Tüm kaynakları gezip haberleri birleştirir; bir kaynağın hatası diğerlerini durdurmaz."""
    hepsi: List[Dict[str, str]] = []
    for ad, url in KAYNAKLAR:
        haberler = kaynak_cek(ad, url)
        hepsi.extend(haberler)
        print(f"[Haber] {ad}: {len(haberler)} haber")
    return hepsi


def _yayin_tarihi_coz(ham: str) -> datetime:
    """
    RFC-822 / ISO-8601 tarihini çözer; çözülemezse ŞU AN döner.

    Şu an döndürmek bilinçli: tarihi okunamayan haberi atmak yerine akışın
    başına koymak, kullanıcı için sessizce kaybolmasından iyidir. Yanlış
    sıralanma riski var ama kaynakların çoğu geçerli tarih veriyor.
    """
    if ham:
        for bicim in (
            "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                t = datetime.strptime(ham.strip(), bicim)
                return t.replace(tzinfo=None)
            except ValueError:
                continue
    return datetime.utcnow()


def haberleri_senkronize_et(db: Session) -> Dict[str, int]:
    """
    Tüm kaynakları çeker, genel piyasa haberlerini `market_news` tablosuna
    yazar ve bir hisseyle eşleşenleri ayrıca `stock_news`e ekler.

    Tekilleştirme URL üzerinden yapılır: aynı haber birden çok kaynakta
    çıkabilir ama URL'i farklıdır; aynı kaynak tekrar çekildiğinde ise URL
    aynıdır. Başlıkla tekilleştirmek farklı haberleri birleştirme riski taşır.
    """
    haberler = tum_kaynaklari_cek()
    if not haberler:
        print("[Haber] Hiçbir kaynaktan haber alınamadı, senkronizasyon atlandı.")
        return {"cekilen": 0, "yeni": 0, "hisse_eslesmesi": 0}

    mevcut_urller = {
        u for (u,) in db.query(models.MarketNews.url).filter(models.MarketNews.url.isnot(None)).all()
    }

    hisseler = [(s.symbol, s.company_name)
                for s in db.query(models.Stock).filter_by(is_active=True).all()]
    eslestirici = HaberEslestirici(hisseler)
    hisse_id = {s.symbol: s.id for s in db.query(models.Stock).all()}

    yeni = 0
    eslesme = 0
    for h in haberler:
        if not h["url"] or h["url"] in mevcut_urller:
            continue
        mevcut_urller.add(h["url"])
        yayin = _yayin_tarihi_coz(h["yayin"])

        db.add(models.MarketNews(
            title=h["baslik"],
            summary=h["ozet"] or None,
            source=h["kaynak"],
            url=h["url"],
            published_at=yayin,
        ))
        yeni += 1

        # Hisse eşleştirmesi (bkz. haber_eslestirme.py — ölçülen kesinlik %100).
        for sembol in eslestirici.eslestir(h["baslik"] + " " + h["ozet"]):
            sid = hisse_id.get(sembol)
            if not sid:
                continue
            zaten_var = (
                db.query(models.StockNews)
                .filter_by(stock_id=sid, url=h["url"])
                .first()
            )
            if zaten_var:
                continue
            db.add(models.StockNews(
                provider="rss",
                stock_id=sid,
                symbol=sembol,
                title=h["baslik"],
                summary=h["ozet"] or None,
                source=h["kaynak"],
                url=h["url"],
                published_at=yayin.isoformat(),
            ))
            eslesme += 1

    # Eski kayıtları temizle — tablo sonsuza kadar büyümemeli.
    esik = datetime.utcnow() - timedelta(days=SAKLAMA_GUNU)
    silinen = (
        db.query(models.MarketNews)
        .filter(models.MarketNews.published_at < esik)
        .delete(synchronize_session=False)
    )

    db.commit()
    print(f"[Haber] {len(haberler)} haber çekildi, {yeni} yeni kayıt, "
          f"{eslesme} hisse eşleşmesi, {silinen} eski kayıt silindi.")
    return {"cekilen": len(haberler), "yeni": yeni, "hisse_eslesmesi": eslesme}
