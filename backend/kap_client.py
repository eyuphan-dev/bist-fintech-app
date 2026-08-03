import requests
from typing import List, Dict, Any
from datetime import datetime, timedelta

# NOT (2026-08-03): Eski entegrasyon iki artık ölü/çalışmayan uç noktayı
# kullanıyordu — "efts.kap.org.tr" domaini artık DNS'te bile çözülmüyor
# (NXDOMAIN) ve "/tr/api/disclosures/member/{symbol}" yolu KAP'ın WAF'ı
# tarafından sessizce bağlantı düşürülerek (connection drop / timeout)
# engelleniyordu. Bu yüzden KAP bildirimleri hiçbir zaman gelmiyordu.
#
# Doğru ve halihazırda çalışan uç nokta "/tr/api/disclosure/members/byCriteria"
# (POST, tarih aralığı + opsiyonel üye OID listesi alır, sembol bazlı filtre
# desteklemez). Sembole göre filtreleme, dönen listedeki stockCodes/
# relatedStocks alanlarına bakılarak istemci tarafında yapılır.
KAP_QUERY_URL = "https://www.kap.org.tr/tr/api/disclosure/members/byCriteria"

# KAP tek istekte en fazla ~2000 kayıt döndürüyor (en güncelden geriye doğru);
# çok geniş tarih aralıkları isteği geçersiz kılmaz ama eski kayıtlar kesilir.
MAX_LOOKBACK_DAYS = 14

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Content-Type": "application/json",
    "Referer": "https://www.kap.org.tr/tr/bildirim-sorgu",
    "Origin": "https://www.kap.org.tr",
}


def _query_disclosures(from_date: datetime, to_date: datetime) -> List[Dict[str, Any]]:
    """KAP'ın genel bildirim akışını (tüm şirketler, tüm hisseler) tarih aralığına göre çeker."""
    body = {
        "fromDate": from_date.strftime("%Y-%m-%d"),
        "toDate": to_date.strftime("%Y-%m-%d"),
        "mkkMemberOidList": [],
        "subjectList": [],
    }
    resp = requests.post(KAP_QUERY_URL, json=body, headers=HEADERS, timeout=8)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def _matching_symbols(item: Dict[str, Any], known_symbols: set) -> set:
    """Bir bildirim kaydının ilgili olduğu, takip ettiğimiz sembolleri döner."""
    matched = set()
    for field in ("stockCodes", "relatedStocks"):
        value = item.get(field)
        if not value:
            continue
        for code in value.split(","):
            code = code.strip().upper()
            if code in known_symbols:
                matched.add(code)
    return matched


def _symbol_matches(item: Dict[str, Any], symbol: str) -> bool:
    return bool(_matching_symbols(item, {symbol.upper()}))


def _to_disclosure_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    date_str = item.get("publishDate") or ""
    index = item.get("disclosureIndex")
    return {
        "title": item.get("summary") or item.get("subject") or "Kamuoyu Bildirimi",
        "date": _format_date(date_str),
        "date_raw": date_str,
        "type": item.get("subject") or item.get("disclosureCategory") or "",
        "company": item.get("kapTitle") or "",
        "url": f"https://www.kap.org.tr/tr/Bildirim/{index}" if index else "",
    }


def fetch_kap_disclosures(symbol: str, limit: int = 8, lookback_days: int = MAX_LOOKBACK_DAYS) -> List[Dict[str, Any]]:
    """
    Verilen BİST sembolü için son KAP bildirimlerini çeker.
    KAP'ın herkese açık API'si sembol bazlı filtre desteklemediğinden (üye OID'i
    gerektirir), tarih aralığındaki TÜM piyasa bildirimleri tek istekte çekilip
    stockCodes/relatedStocks alanlarına göre istemci tarafında filtrelenir.
    """
    now = datetime.utcnow()
    try:
        items = _query_disclosures(now - timedelta(days=lookback_days), now)
    except Exception as e:
        print(f"KAP bildirim sorgusu başarısız ({symbol}): {str(e)}")
        return []

    matches = [item for item in items if _symbol_matches(item, symbol)]
    return [_to_disclosure_dict(item) for item in matches[:limit]]


def _format_date(date_str: str) -> str:
    """Formats a date string from KAP API to a human-readable format."""
    if not date_str:
        return ""

    # Try common date formats
    formats = [
        "%d.%m.%Y %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:19] if " " in fmt or "T" in fmt else date_str[:10], fmt)
            return dt.strftime("%d.%m.%Y")
        except Exception:
            pass

    return date_str[:10] if len(date_str) >= 10 else date_str

def get_kap_search_url(symbol: str) -> str:
    """Returns the direct KAP search URL for a symbol."""
    return f"https://www.kap.org.tr/tr/bildirim-sorgu?member={symbol}"


def fetch_kap_news(db, limit: int = 20) -> list:
    """
    Takip edilen tüm aktif hisseler için genel KAP bildirim akışını çeker ve
    kap_notifications tablosuna yazar. Kullanıcı arayüzünde "Piyasa Haberleri"
    (genel akış) sekmesi için kullanılır.

    Önceki sürüm her hisse için ayrı ayrı istek atıyordu (N istek); artık tek
    bir POST isteğiyle son 2 günün TÜM piyasa bildirimleri çekilip, takip
    edilen sembollere göre istemci tarafında eşleştiriliyor — hem daha hızlı
    hem de KAP'ın WAF'ını gereksiz yere zorlamıyor.
    """
    import models

    now = datetime.utcnow()
    try:
        items = _query_disclosures(now - timedelta(days=2), now)
    except Exception as e:
        print(f"[KAP] Genel bildirim akışı çekilemedi: {e}")
        return []

    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    symbol_to_stock = {s.symbol.upper(): s for s in stocks}
    known_symbols = set(symbol_to_stock.keys())

    notifications = []
    newly_created = []

    for item in items:
        matched_symbols = _matching_symbols(item, known_symbols)
        if not matched_symbols:
            continue

        d = _to_disclosure_dict(item)
        publish_date = _parse_disclosure_date(d.get("date_raw") or d.get("date", ""))

        for sym in matched_symbols:
            stock = symbol_to_stock[sym]
            exists = (
                db.query(models.KapNotification)
                .filter_by(stock_id=stock.id, title=d.get("title", ""), publish_date=publish_date)
                .first()
            )
            if not exists:
                notif = models.KapNotification(
                    stock_id=stock.id,
                    symbol=stock.symbol,
                    title=d.get("title", "Kamuoyu Bildirimi"),
                    summary=d.get("type", ""),
                    kap_url=d.get("url", ""),
                    publish_date=publish_date,
                )
                db.add(notif)
                notifications.append(d)
                newly_created.append(notif)

    db.commit()

    # Bu hisseleri izleyen (notify_kap=True) kullanıcılar için bildirim oluştur
    try:
        from notifications import check_kap_triggers
        check_kap_triggers(db, newly_created)
    except Exception as e:
        print(f"[KAP] İzleyici bildirimi oluşturma hatası: {e}")

    return notifications[:limit]


def _parse_disclosure_date(date_str: str):
    if not date_str:
        return datetime.utcnow()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            has_time = " " in fmt or "T" in fmt
            return datetime.strptime(date_str[:19] if has_time else date_str[:10], fmt)
        except Exception:
            continue
    return datetime.utcnow()
