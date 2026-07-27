import threading
from datetime import datetime
from typing import Dict, Any, Optional

_cache_lock = threading.Lock()
# format: { symbol: { "price": float, "volume": int, "recorded_at": datetime } }
_latest_prices: Dict[str, Dict[str, Any]] = {}

def set_latest_price(symbol: str, price: float, volume: int, recorded_at: datetime):
    with _cache_lock:
        _latest_prices[symbol] = {
            "price": price,
            "volume": volume,
            "recorded_at": recorded_at
        }

def get_latest_price(symbol: str) -> Optional[Dict[str, Any]]:
    with _cache_lock:
        return _latest_prices.get(symbol)

def get_all_latest_prices() -> Dict[str, Dict[str, Any]]:
    with _cache_lock:
        # Return a copy to prevent race conditions during iteration
        return {k: dict(v) for k, v in _latest_prices.items()}


# --- Hisse Haberleri Önbelleği (TTL'li) ---
# Her istekte yfinance'a canlı gitmek yerine (yavaş dış API), sonuçlar bir süre
# önbellekte tutulur. Bu, KAP taramasında yaşanan "her istekte canlı tarama"
# donma sorununun haberler için de tekrarlanmasını önler.
_news_cache: Dict[str, Dict[str, Any]] = {}
NEWS_CACHE_TTL_SECONDS = 20 * 60  # 20 dakika


def get_cached_news(symbol: str):
    with _cache_lock:
        entry = _news_cache.get(symbol)
        if not entry:
            return None
        age = (datetime.utcnow() - entry["cached_at"]).total_seconds()
        if age > NEWS_CACHE_TTL_SECONDS:
            return None
        return entry["items"]


def set_cached_news(symbol: str, items):
    with _cache_lock:
        _news_cache[symbol] = {"items": items, "cached_at": datetime.utcnow()}
