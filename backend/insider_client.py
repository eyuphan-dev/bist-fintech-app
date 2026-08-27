"""
insider_client.py
------------------
KAP üzerinden "Pay Geri Alımı / Yönetici ve İlgili Kişilerin İşlemleri"
bildirimlerini (içeriden öğrenenlerin ticareti) çekip insider_trades tablosuna yazar.

KAP'ın bu veriler için resmi/açık bir REST API'si yoktur; bu istemci
kap_client.py ile aynı savunmacı (defensive) yaklaşımı izler: uç değişirse
veya erişilemezse sessizce boş liste döner, uygulamayı düşürmez.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

import models
from kap_client import _query_disclosures, _symbol_matches, _matching_symbols
from text_utils import tr_lower

# NOT (2026-08-03): Eski "efts.kap.org.tr" uç noktası artık DNS'te çözülmüyor
# (bkz. kap_client.py) — bu istemci de hiçbir zaman veri döndürmüyordu.
# kap_client.py'deki çalışan genel bildirim sorgusu kullanılıp, KAP'ın
# "Pay Alım Satım Bildirimi" (disclosureClass='DKB' veya konu başlığı eşleşen)
# kayıtları filtrelenir. Miktar/fiyat bilgisi yalnızca ekli PDF içinde yer
# aldığından (API JSON'unda yok) bu alanlar şimdilik 0 olarak kaydedilir —
# asıl amaç "içeriden bir işlem oldu mu, ne zaman, kim" bilgisini doğru
# çekebilmek; PDF'ten tutar ayrıştırma ayrı bir iyileştirme konusu.
INSIDER_SUBJECT_KEYWORDS = ["pay alım satım", "içeriden öğrenen", "pay geri alım", "yönetici işlem"]

# Türkçe "satış" varyasyonları içeren metinlerde önce SATIM'a bakılır ki
# "alım satım bildirimi" gibi genel başlıklarda yanlışlıkla ALIM'a düşülmesin.
SELL_KEYWORDS = ["satılmış", "satış", "sattı", "satım işlemi"]
BUY_KEYWORDS = ["satın al", "alım işlemi", "alınmış", "aldı"]


def fetch_insider_trades(db: Session, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Belirli bir sembol için KAP'tan içeriden öğrenenler ticareti bildirimlerini çeker,
    ayrıştırabildiklerini insider_trades tablosuna yazar ve döndürür.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return []

    results: List[Dict[str, Any]] = []
    try:
        now = datetime.utcnow()
        items = _query_disclosures(now - timedelta(days=30), now)
        for item in items:
            if not _symbol_matches(item, symbol.upper()):
                continue
            parsed = _parse_insider_item(item, symbol.upper())
            if parsed:
                # kapTitle bazen gönderici olarak jenerik "Kamuyu Aydınlatma Platformu"
                # döner (KAP'a üçüncü taraf ileten kayıtlarda); bildirim zaten tek bir
                # sembole göre süzüldüğü için gerçek şirket adını kullanmak daha doğru.
                if not parsed["title_person"] or "kamuyu aydınlatma" in parsed["title_person"].lower():
                    parsed["title_person"] = stock.company_name or symbol.upper()
                results.append(parsed)
            if len(results) >= limit:
                break
    except Exception as e:
        print(f"[InsiderClient] KAP içeriden öğrenenler sorgusu başarısız ({symbol}): {e}")

    # DB'ye yaz (varsa güncelleme yapılmaz, sadece yeni kayıt eklenir)
    for r in results:
        try:
            exists = (
                db.query(models.InsiderTrade)
                .filter_by(stock_id=stock.id, title_person=r["title_person"], trade_date=r["trade_date"])
                .first()
            )
            if not exists:
                db.add(models.InsiderTrade(
                    stock_id=stock.id,
                    symbol=symbol.upper(),
                    title_person=r["title_person"],
                    trade_type=r["trade_type"],
                    quantity=r["quantity"],
                    price=r["price"],
                    trade_date=r["trade_date"],
                ))
        except Exception as e:
            print(f"[InsiderClient] Kayıt yazma hatası: {e}")

    db.commit()
    return results


def refresh_all_insider_trades(db: Session, lookback_days: int = 30) -> int:
    """
    TÜM aktif hisseler için içeriden öğrenenler ticaretini TEK KAP çağrısıyla tazeler.

    NEDEN GEREKLİ: fetch_insider_trades() yalnızca kullanıcı bir hissenin detay
    sayfasını açtığında çalışıyordu (bkz. main.py /api/stocks/{symbol}/insider-trades).
    165 hisselik katalogda kimse ziyaret etmediği hisseler için hiç veri
    çekilmiyordu — üretimde yalnızca 5 hissede 7 kayıt vardı. Ayrıca sayfa
    ziyaretinde çağrılsaydı bile her sembol için AYRI bir KAP sorgusu atardı;
    `_query_disclosures` zaten TÜM şirketlerin bildirimini tek seferde
    döndürüyor, yani 165 hisse için 165 istek yerine TEK istek yeterli.

    Bu fonksiyon o tek isteği atar, sonucu tüm aktif hisselere dağıtır.
    """
    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    by_symbol = {s.symbol.upper(): s for s in stocks}
    if not by_symbol:
        return 0

    try:
        now = datetime.utcnow()
        items = _query_disclosures(now - timedelta(days=lookback_days), now)
    except Exception as e:
        print(f"[InsiderClient] Toplu KAP sorgusu başarısız: {e}")
        return 0

    yazilan = 0
    for item in items:
        eslesen = _matching_symbols(item, set(by_symbol.keys()))
        if not eslesen:
            continue
        for symbol in eslesen:
            stock = by_symbol[symbol]
            parsed = _parse_insider_item(item, symbol)
            if not parsed:
                continue
            if not parsed["title_person"] or "kamuyu aydınlatma" in parsed["title_person"].lower():
                parsed["title_person"] = stock.company_name or symbol

            exists = (
                db.query(models.InsiderTrade)
                .filter_by(stock_id=stock.id, title_person=parsed["title_person"],
                          trade_date=parsed["trade_date"])
                .first()
            )
            if exists:
                continue
            try:
                db.add(models.InsiderTrade(
                    stock_id=stock.id, symbol=symbol,
                    title_person=parsed["title_person"], trade_type=parsed["trade_type"],
                    quantity=parsed["quantity"], price=parsed["price"],
                    trade_date=parsed["trade_date"],
                ))
                yazilan += 1
            except Exception as e:
                print(f"[InsiderClient] Kayıt yazma hatası ({symbol}): {e}")

    db.commit()
    print(f"[InsiderClient] Toplu tarama: {len(items)} bildirim tarandı, {yazilan} yeni kayıt.")
    return yazilan


def _parse_insider_item(item: Dict, symbol: str) -> Optional[Dict[str, Any]]:
    try:
        # tr_lower KULLAN, .lower() DEĞİL: KAP başlıkları "İçeriden Öğrenenler
        # İşlemi" gibi büyük İ ile geliyor; .lower() bunu ASCII "i" değil görünmez
        # birleştirici işaretli bir "i"ye çevirip anahtar kelime eşleşmesini
        # kırıyordu (bkz. text_utils.py). Bu yüzden 165 hisselik katalogda
        # içeriden öğrenen verisi neredeyse hiç birikmiyordu.
        subject = tr_lower(item.get("subject") or "")
        summary = tr_lower(item.get("summary") or "")
        combined = f"{subject} {summary}"
        if not any(k in combined for k in INSIDER_SUBJECT_KEYWORDS):
            return None

        if any(k in combined for k in SELL_KEYWORDS):
            trade_type = "SATIM"
        elif any(k in combined for k in BUY_KEYWORDS):
            trade_type = "ALIM"
        else:
            trade_type = "ALIM"  # varsayılan: KAP "pay alım satım bildirimi" genelde alım tarafını raporlar

        trade_date = _parse_date(item.get("publishDate", "")) or datetime.utcnow()

        return {
            "title_person": item.get("kapTitle") or "Yönetici / İlgili Taraf",
            "trade_type": trade_type,
            # Miktar/fiyat yalnızca KAP'ın ekli PDF'inde yer alıyor (API JSON'unda yok);
            # burada 0 olarak kaydedilir, badge yalnızca "işlem oldu mu" bilgisini kullanır.
            "quantity": 0.0,
            "price": 0.0,
            "trade_date": trade_date,
        }
    except Exception:
        return None


def _parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt, length in (("%d.%m.%Y %H:%M:%S", 19), ("%Y-%m-%dT%H:%M:%S", 19), ("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10), ("%d.%m.%Y", 10)):
        try:
            return datetime.strptime(date_str[:length], fmt)
        except Exception:
            continue
    return None


def get_recent_insider_buys(db: Session, stock_id: int, days: int = 30) -> List[models.InsiderTrade]:
    """'Patron Hissede Alımda!' rozeti için son N gündeki ALIM kayıtlarını döner."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(models.InsiderTrade)
        .filter(
            models.InsiderTrade.stock_id == stock_id,
            models.InsiderTrade.trade_type == "ALIM",
            models.InsiderTrade.trade_date >= cutoff,
        )
        .order_by(models.InsiderTrade.trade_date.desc())
        .all()
    )
