"""
insider_client.py
------------------
KAP üzerinden "Pay Geri Alımı / Yönetici ve İlgili Kişilerin İşlemleri"
bildirimlerini (içeriden öğrenenlerin ticareti) çekip insider_trades tablosuna yazar.

KAP'ın bu veriler için resmi/açık bir REST API'si yoktur; bu istemci
kap_client.py ile aynı savunmacı (defensive) yaklaşımı izler: uç değişirse
veya erişilemezse sessizce boş liste döner, uygulamayı düşürmez.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from sqlalchemy.orm import Session

import models

KAP_INSIDER_SEARCH_URL = "https://efts.kap.org.tr/BIST-AJAX-EFT/AjaxSearchV3"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.kap.org.tr/",
    "Origin": "https://www.kap.org.tr",
}

# KAP bildirim tipi anahtar kelimeleri: "Pay Geri Alım", "İçeriden Öğrenenler" vb.
INSIDER_KEYWORDS = ["içeriden öğrenen", "pay geri alım", "yönetim kurulu üyesi", "yönetici işlem"]


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
        params = {
            "ftype": "searchResultBulletin",
            "term": f"{symbol.upper()} içeriden öğrenenler",
            "page": 1,
            "perPage": limit,
        }
        resp = requests.get(KAP_INSIDER_SEARCH_URL, params=params, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("data", {}).get("current", []) or data.get("data", []) or []
            for item in items[:limit]:
                parsed = _parse_insider_item(item, symbol.upper())
                if parsed:
                    results.append(parsed)
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
        title = item.get("title", "") or item.get("subject", "") or ""
        title_lower = title.lower()
        if not any(k in title_lower for k in INSIDER_KEYWORDS):
            return None

        trade_type = "ALIM" if any(k in title_lower for k in ["alım", "alim", "satın"]) else "SATIM"

        date_str = item.get("disclosureDate", "") or item.get("publishDate", "")
        trade_date = _parse_date(date_str) or datetime.utcnow()

        return {
            "title_person": item.get("memberName", "") or item.get("companyName", "") or "Yönetici / İlgili Taraf",
            "trade_type": trade_type,
            "quantity": float(item.get("quantity", 0) or 0),
            "price": float(item.get("price", 0) or 0),
            "trade_date": trade_date,
        }
    except Exception:
        return None


def _parse_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt, length in (("%Y-%m-%dT%H:%M:%S", 19), ("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d", 10), ("%d.%m.%Y", 10)):
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
