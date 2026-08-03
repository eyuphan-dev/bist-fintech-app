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
from kap_client import _query_disclosures, _symbol_matches

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


def _parse_insider_item(item: Dict, symbol: str) -> Optional[Dict[str, Any]]:
    try:
        subject = (item.get("subject") or "").lower()
        summary = (item.get("summary") or "").lower()
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
