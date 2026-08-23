import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from typing import Any, Dict, List, Optional, Tuple

from yf_retry import call_with_retry

def _safe_previous_close(ticker: "yf.Ticker", symbol: str) -> Optional[float]:
    """
    Yahoo'nun kendi "önceki kapanış" referansını (fast_info.previousClose) çeker.
    Bu değer, BİST'in tedbir/taban-tavan gibi kurallarına göre borsanın resmi
    referans fiyatını yansıtır; kendi stock_prices_daily tablomuzdan türettiğimiz
    "son geçerli günlük bar" değerinden daha güvenilirdir — özellikle bir hissenin
    günlük kapanışı birkaç gündür oluşmadığı (tedbir/az işlem gören) durumlarda
    kendi hesabımız günler öncesine giderken Yahoo doğru referansı veriyor.
    ticker.history()'den SONRA çağrıldığında ek ağ isteği YARATMAZ (aynı session
    üzerinden anlık dönüyor) — bu yüzden mevcut price_history çağrısının hemen
    ardından, ayrı bir retry/backoff olmadan "best effort" çağrılır.
    """
    try:
        fi = ticker.fast_info
        prev_close = fi.get("previousClose") if hasattr(fi, "get") else fi.previous_close
        if prev_close and prev_close == prev_close:  # NaN kontrolü (NaN != NaN)
            return round(float(prev_close), 2)
    except Exception as e:
        print(f"[yfinance_client] previousClose alınamadı ({symbol}): {e}")
    return None


def fetch_current_price(symbol: str) -> Optional[Dict[str, Any]]:
    """
    BIST hissesi için güncel fiyat, hacim, önceki kapanış ve SEANSIN açılış/
    yüksek/düşük değerlerini döner.

    Açılış/yüksek/düşük neden buradan geliyor: daha önce bu değerler kendi
    kaydettiğimiz tik geçmişinden türetiliyordu ve yanlıştı — tikler yalnızca
    scheduler çalışırken yazıldığı için "açılış" gerçekte ilk KAYDEDİLEN fiyat
    oluyordu (backend seans ortasında yeniden başlarsa açılış o an oluyordu).
    Gün içi barların tamamından hesaplayınca seansın gerçek değerleri elde edilir.

    Returns: {'price','volume','previous_close','open','high','low'} veya None
    """
    yahoo_symbol = f"{symbol}.IS"
    try:
        ticker = yf.Ticker(yahoo_symbol)
        # Fetch the last 1 day at 5-minute intervals to get the latest close
        history = call_with_retry(
            lambda: ticker.history(period="1d", interval="5m"),
            attempts=2, label=f"{symbol}.price_history",
        )
        if not history.empty:
            last_row = history.iloc[-1]
            return {
                "price": round(float(last_row["Close"]), 2),
                "volume": int(last_row["Volume"]),
                "previous_close": _safe_previous_close(ticker, symbol),
                # Seansın tamamı üzerinden: ilk barın açılışı, tüm barların en yüksek/en düşüğü.
                "open": round(float(history.iloc[0]["Open"]), 2),
                "high": round(float(history["High"].max()), 2),
                "low": round(float(history["Low"].min()), 2),
            }

        # Fallback to info if history is empty (e.g. pre-market or post-market)
        info = call_with_retry(lambda: ticker.info, attempts=2, label=f"{symbol}.price_info")
        price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
        volume = info.get("regularMarketVolume") or info.get("volume") or 0
        if price:
            def _f(key):
                v = info.get(key)
                return round(float(v), 2) if v is not None else None
            return {
                "price": round(float(price), 2),
                "volume": int(volume),
                "previous_close": _safe_previous_close(ticker, symbol),
                "open": _f("regularMarketOpen"),
                "high": _f("regularMarketDayHigh"),
                "low": _f("regularMarketDayLow"),
            }

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
        raw_news = call_with_retry(lambda: ticker.news, attempts=2, label=f"{symbol}.news") or []
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


def fetch_daily_history(symbol: str, period: str = "5y") -> List[Dict]:
    """
    Uzun vadeli grafik seçenekleri (1H/1A/1Y/5Y) için GÜNLÜK OHLCV geçmişini çeker.
    fetch_historical_prices'tan farkı: sadece kapanış değil OHLC'nin tamamını
    ve datetime yerine saf date döndürür (stock_prices_daily tablosuyla birebir eşleşir).
    """
    yahoo_symbol = f"{symbol}.IS"
    bars: List[Dict] = []
    try:
        ticker = yf.Ticker(yahoo_symbol)
        history = call_with_retry(
            lambda: ticker.history(period=period, interval="1d"),
            attempts=2, label=f"{symbol}.daily_history",
        )
        for index, row in history.iterrows():
            # Gün henüz kapanmadıysa (bugünün barı, borsa açıkken) yfinance bazen
            # Close için NaN döndürüyor — stock_prices_daily.close NOT NULL olduğundan
            # bu barı atlamak gerekiyor (aksi halde DB insert'i IntegrityError ile patlar).
            if not pd.notna(row["Close"]):
                continue
            bars.append({
                "trade_date": index.to_pydatetime().date(),
                "open": round(float(row["Open"]), 2) if pd.notna(row["Open"]) else None,
                "high": round(float(row["High"]), 2) if pd.notna(row["High"]) else None,
                "low": round(float(row["Low"]), 2) if pd.notna(row["Low"]) else None,
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]) if pd.notna(row["Volume"]) else 0,
            })
    except Exception as e:
        print(f"Error fetching daily history for {symbol}: {str(e)}")
    return bars


def fetch_historical_prices(symbol: str, period: str = "1mo", interval: str = "1d") -> List[Dict]:
    """
    Fetches historical price data for a BIST stock.
    Returns: List of dicts with price, volume, recorded_at
    """
    yahoo_symbol = f"{symbol}.IS"
    prices = []
    try:
        ticker = yf.Ticker(yahoo_symbol)
        history = call_with_retry(
            lambda: ticker.history(period=period, interval=interval),
            attempts=2, label=f"{symbol}.hist_prices",
        )
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


# ---------------------------------------------------------------------------
# Toplu fiyat çekimi
# ---------------------------------------------------------------------------
# NEDEN: fetch_current_price hisse başına ayrı HTTP isteği yapar. Katalog 43
# hisseyken (istek başına ~0.8 sn + 0.4 sn bekleme) bir tur ~1 dakika sürüyordu
# ve 5 dakikalık tetikleme aralığına rahat sığıyordu. Katalog 165 hisseye
# çıkınca aynı yaklaşım ~3.5 dakikaya çıkıp aralığı doldurmaya başlıyordu:
# Yahoo bir gün yavaşladığında turlar üst üste biner, max_instances=1 yüzünden
# tetiklemeler sessizce atlanır ve fiyatlar bayatlardı.
#
# yf.download tek istekte ONLARCA sembol döndürür. 165 hisse, 40'lık parçalarda
# 5 istekle çekilir — yani ~330 istek yerine ~10 istek.
BATCH_SIZE = 40


def fetch_current_prices_batch(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Birden çok hissenin güncel fiyat/hacim/açılış/yüksek/düşük/önceki kapanış
    değerlerini toplu çeker.

    Dönen sözlükte YALNIZCA veri gelen semboller bulunur; eksik kalanlar için
    çağıran tarafın tek tek `fetch_current_price` ile denemesi beklenir.
    """
    out: Dict[str, Dict[str, Any]] = {}
    if not symbols:
        return out

    for i in range(0, len(symbols), BATCH_SIZE):
        chunk = symbols[i : i + BATCH_SIZE]
        tickers = [f"{s}.IS" for s in chunk]
        try:
            # Gün içi barlar: seansın açılış/yüksek/düşük/son değeri buradan.
            intraday = call_with_retry(
                lambda: yf.download(
                    tickers, period="1d", interval="5m",
                    group_by="ticker", auto_adjust=False,
                    progress=False, threads=False,
                ),
                attempts=2, label=f"batch_intraday[{i}]",
            )
            # Önceki kapanış: 5 günlük günlük bar. 2 gün yetmez — araya hafta
            # sonu veya tatil girerse önceki iş günü elde kalmaz.
            daily = call_with_retry(
                lambda: yf.download(
                    tickers, period="5d", interval="1d",
                    group_by="ticker", auto_adjust=False,
                    progress=False, threads=False,
                ),
                attempts=2, label=f"batch_daily[{i}]",
            )
        except Exception as e:
            print(f"[yfinance_client] toplu çekim başarısız ({chunk[0]}...): {e}")
            continue

        for symbol in chunk:
            yahoo = f"{symbol}.IS"
            try:
                # Tek sembollük indirmede yfinance sütunları düzleştirir;
                # çok sembollüde ilk seviye ticker olur. İkisi de desteklenir.
                bars = intraday[yahoo] if yahoo in getattr(intraday, "columns", []) else intraday
                bars = bars.dropna(subset=["Close"])
                if bars.empty:
                    continue

                last = bars.iloc[-1]
                prev_close = None
                try:
                    dbars = daily[yahoo] if yahoo in getattr(daily, "columns", []) else daily
                    dbars = dbars.dropna(subset=["Close"])
                    # Son satır BUGÜN olabilir; önceki kapanış bir öncekidir.
                    if len(dbars) >= 2:
                        prev_close = round(float(dbars["Close"].iloc[-2]), 2)
                except Exception:
                    prev_close = None

                out[symbol] = {
                    "price": round(float(last["Close"]), 2),
                    "volume": int(last["Volume"]) if last["Volume"] == last["Volume"] else 0,
                    "previous_close": prev_close,
                    "open": round(float(bars.iloc[0]["Open"]), 2),
                    "high": round(float(bars["High"].max()), 2),
                    "low": round(float(bars["Low"].min()), 2),
                }
            except Exception:
                # Tek bir sembolün bozuk gelmesi tüm partiyi düşürmemeli.
                continue

    return out
