import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Optional, Tuple

def fetch_current_price(symbol: str) -> Optional[Tuple[float, int]]:
    """
    Fetches the current price and volume for a BIST stock from Yahoo Finance.
    Returns: Tuple[price, volume] or None
    """
    yahoo_symbol = f"{symbol}.IS"
    try:
        ticker = yf.Ticker(yahoo_symbol)
        # Fetch the last 1 day at 5-minute intervals to get the latest close
        history = ticker.history(period="1d", interval="5m")
        if not history.empty:
            last_row = history.iloc[-1]
            price = round(float(last_row["Close"]), 2)
            volume = int(last_row["Volume"])
            return price, volume
        
        # Fallback to info if history is empty (e.g. pre-market or post-market)
        info = ticker.info
        price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
        volume = info.get("regularMarketVolume") or info.get("volume") or 0
        if price:
            return round(float(price), 2), int(volume)
            
    except Exception as e:
        print(f"Error fetching current price for {symbol}: {str(e)}")
    return None

def fetch_stock_news(symbol: str, limit: int = 8) -> List[Dict]:
    """
    Fetches recent news headlines for a BIST stock from Yahoo Finance (yfinance).
    Returns: List of dicts with title, summary, source, url, published_at, thumbnail.
    """
    yahoo_symbol = f"{symbol}.IS"
    items: List[Dict] = []
    try:
        ticker = yf.Ticker(yahoo_symbol)
        raw_news = ticker.news or []
        for entry in raw_news[:limit]:
            # yfinance sürümüne göre haber öğesi ya doğrudan ya da "content" altında gelir.
            content = entry.get("content", entry) if isinstance(entry, dict) else {}
            title = content.get("title")
            if not title:
                continue

            provider = (
                (content.get("provider") or {}).get("displayName")
                or content.get("publisher")
                or ""
            )
            url = (
                (content.get("canonicalUrl") or {}).get("url")
                or (content.get("clickThroughUrl") or {}).get("url")
                or content.get("link")
                or ""
            )

            thumbnail = None
            thumb = content.get("thumbnail")
            if isinstance(thumb, dict):
                resolutions = thumb.get("resolutions") or []
                if resolutions:
                    thumbnail = resolutions[0].get("url")

            published_at = content.get("pubDate") or content.get("displayTime")
            epoch_time = content.get("providerPublishTime")
            if not published_at and epoch_time:
                try:
                    published_at = datetime.utcfromtimestamp(int(epoch_time)).isoformat() + "Z"
                except Exception:
                    published_at = None

            items.append({
                "title": title,
                "summary": content.get("summary") or content.get("description") or "",
                "source": provider,
                "url": url,
                "published_at": published_at,
                "thumbnail": thumbnail,
            })
    except Exception as e:
        print(f"Error fetching news for {symbol}: {str(e)}")
    return items


def fetch_historical_prices(symbol: str, period: str = "1mo", interval: str = "1d") -> List[Dict]:
    """
    Fetches historical price data for a BIST stock.
    Returns: List of dicts with price, volume, recorded_at
    """
    yahoo_symbol = f"{symbol}.IS"
    prices = []
    try:
        ticker = yf.Ticker(yahoo_symbol)
        history = ticker.history(period=period, interval=interval)
        for index, row in history.iterrows():
            # index is Timestamp
            recorded_at = index.to_pydatetime()
            prices.append({
                "price": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
                "recorded_at": recorded_at
            })
    except Exception as e:
        print(f"Error fetching historical prices for {symbol}: {str(e)}")
    return prices
