import requests
from typing import List, Dict, Any, Optional
from datetime import datetime

# KAP public disclosure API (undocumented but publicly accessible)
KAP_DISCLOSURE_URL = "https://efts.kap.org.tr/BIST-AJAX-EFT/AjaxSearchV3"
KAP_MEMBER_DISCLOSURES_URL = "https://www.kap.org.tr/tr/api/disclosures/member"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.kap.org.tr/",
    "Origin": "https://www.kap.org.tr",
}

def fetch_kap_disclosures(symbol: str, limit: int = 8) -> List[Dict[str, Any]]:
    """
    Fetches recent KAP public disclosures for a given BIST stock symbol.
    Uses the KAP EFTS (Electronic Filing and Trading System) public search API.
    Returns a list of disclosure dicts.
    """
    disclosures = []
    
    try:
        # Method 1: Try the EFTS search endpoint
        params = {
            "ftype": "searchResultBulletin",
            "term": symbol,
            "page": 1,
            "perPage": limit
        }
        
        resp = requests.get(
            KAP_DISCLOSURE_URL,
            params=params,
            headers=HEADERS,
            timeout=4
        )
        
        if resp.status_code == 200:
            data = resp.json()
            # EFTS returns results in a nested structure
            items = data.get("data", {}).get("current", []) or data.get("data", []) or []
            
            if isinstance(items, list) and len(items) > 0:
                for item in items[:limit]:
                    disclosure = _parse_efts_disclosure(item, symbol)
                    if disclosure:
                        disclosures.append(disclosure)
                        
                if disclosures:
                    return disclosures
                    
    except Exception as e:
        print(f"KAP EFTS fetch failed for {symbol}: {str(e)}")

    try:
        # Method 2: Try the KAP member disclosures API directly
        resp2 = requests.get(
            f"{KAP_MEMBER_DISCLOSURES_URL}/{symbol}",
            headers=HEADERS,
            timeout=4
        )
        
        if resp2.status_code == 200:
            data2 = resp2.json()
            items2 = data2 if isinstance(data2, list) else data2.get("data", [])
            
            for item in items2[:limit]:
                disclosure = _parse_member_disclosure(item, symbol)
                if disclosure:
                    disclosures.append(disclosure)
                    
    except Exception as e:
        print(f"KAP member API fetch failed for {symbol}: {str(e)}")

    return disclosures

def _parse_efts_disclosure(item: Dict, symbol: str) -> Optional[Dict[str, Any]]:
    """Parse a disclosure from the EFTS search API response."""
    try:
        # The EFTS structure typically looks like this
        title = (
            item.get("title", "") or 
            item.get("bildirimTipiAciklama", "") or 
            item.get("subject", "") or
            "Kamuoyu Bildirimi"
        )
        
        date_str = (
            item.get("disclosureDate", "") or
            item.get("publishDate", "") or
            item.get("publishedAt", "") or
            item.get("date", "")
        )
        
        formatted_date = _format_date(date_str)
        
        url = item.get("disclosureLink", "") or item.get("url", "") or item.get("link", "")
        if url and not url.startswith("http"):
            url = f"https://www.kap.org.tr{url}"
            
        disclosure_type = (
            item.get("disclosureType", "") or 
            item.get("bildirimTipi", "") or
            item.get("type", "")
        )
        
        company_name = (
            item.get("companyName", "") or 
            item.get("sirketAdi", "") or
            item.get("memberName", "")
        )
        
        return {
            "title": title,
            "date": formatted_date,
            "date_raw": date_str,
            "type": disclosure_type,
            "company": company_name or symbol,
            "url": url,
        }
    except Exception:
        return None

def _parse_member_disclosure(item: Dict, symbol: str) -> Optional[Dict[str, Any]]:
    """Parse a disclosure from the member API response."""
    try:
        title = (
            item.get("bildirimTipiAciklama", "") or 
            item.get("subject", "") or
            item.get("title", "") or
            "Kamuoyu Bildirimi"
        )
        
        date_str = (
            item.get("publishDate", "") or
            item.get("disclosureDate", "") or
            item.get("tarih", "")
        )
        
        formatted_date = _format_date(date_str)
        
        url = item.get("url", "") or item.get("disclosureLink", "")
        if url and not url.startswith("http"):
            url = f"https://www.kap.org.tr{url}"
            
        return {
            "title": title,
            "date": formatted_date,
            "date_raw": date_str,
            "type": item.get("bildirimTipi", "") or item.get("type", ""),
            "company": item.get("memberName", symbol),
            "url": url,
        }
    except Exception:
        return None

def _format_date(date_str: str) -> str:
    """Formats a date string from KAP API to a human-readable format."""
    if not date_str:
        return ""
    
    # Try common date formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y",
        "%d/%m/%Y",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:19], fmt[:len(date_str[:19].split(" ")[0]) + (10 if "T" in date_str or " " in date_str else 0)])
            return dt.strftime("%d.%m.%Y")
        except:
            pass
    
    # If no format matched, try to extract the date part directly
    if len(date_str) >= 10:
        try:
            # Try parsing the first 10 characters
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return dt.strftime("%d.%m.%Y")
        except:
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
    """
    import models

    notifications = []
    newly_created = []
    stocks = db.query(models.Stock).filter_by(is_active=True).all()

    for stock in stocks:
        disclosures = fetch_kap_disclosures(stock.symbol, limit=3)
        for d in disclosures:
            publish_date = _parse_disclosure_date(d.get("date_raw") or d.get("date", ""))
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
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str[:19] if "T" in fmt or " " in fmt else date_str[:10], fmt)
        except Exception:
            continue
    return datetime.utcnow()
