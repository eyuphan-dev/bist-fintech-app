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
