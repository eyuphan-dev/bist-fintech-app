"""
yf_retry.py
-----------
Yahoo Finance (yfinance) "429 Too Many Requests" hatalarına karşı ortak
retry/backoff yardımcı fonksiyonu.

Neden gerekli: Sunucu tek bir egress IP üzerinden çalışıyor. Scheduler her
5 dakikada tüm aktif hisseleri sırayla çektiği için (bkz. scheduler.py),
Yahoo bu IP'yi kısa süreli olarak "rate limited" damgalayabiliyor. Bu durumda
kullanıcı "Analiz Tazele" gibi anlık bir istek attığında da aynı IP üzerinden
gittiği için 429 alıyor. Çözüm: üstel bekleme ile birkaç kez yeniden dene —
Yahoo'nun rate limit penceresi genelde saniyeler mertebesinde kısa sürer.
"""

import os
import random
import time
from typing import Callable, TypeVar

import yfinance as yf

T = TypeVar("T")

RATE_LIMIT_MARKERS = ("Too Many Requests", "Rate limited", "429")


def configure_yfinance() -> None:
    """
    Uygulama başlangıcında bir kez çağrılır.

    Render gibi paylaşımlı bulut sağlayıcıların egress IP'leri, çok sayıda
    yfinance kullanıcısı tarafından paylaşıldığından Yahoo Finance tarafında
    kalıcı/uzun süreli olarak engellenebiliyor (basit rate-limit'ten farklı:
    yeniden denemek bile çözmüyor, "boş yanıt" ya da 429 dönmeye devam ediyor).
    Bu durumda tek gerçek çözüm istekleri farklı bir IP üzerinden (proxy)
    yönlendirmektir. YF_PROXY_URL ortam değişkeni tanımlıysa (örn.
    "http://user:pass@host:port") tüm yfinance istekleri bu proxy üzerinden
    gider; tanımlı değilse davranış öncekiyle aynı kalır.
    """
    proxy_url = os.environ.get("YF_PROXY_URL")
    if proxy_url:
        yf.config.network.proxy = proxy_url
        print("[yf_retry] yfinance istekleri YF_PROXY_URL üzerinden yönlendiriliyor.")
    yf.config.network.retries = 2


def is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc)
    return any(marker.lower() in msg.lower() for marker in RATE_LIMIT_MARKERS)


def call_with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay: float = 3.0,
    label: str = "",
) -> T:
    """
    fn'i çağırır; "Too Many Requests" / rate limit hatası alırsa üstel
    bekleme (+ jitter) ile yeniden dener. Rate limit dışı hatalarda hemen
    yükseltir (gereksiz beklemeyi önlemek için).
    """
    last_exc: Exception = RuntimeError("call_with_retry: fn hiç çağrılmadı")
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if not is_rate_limit_error(e) or attempt == attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1.5)
            print(
                f"[yf_retry] Rate limit ({label or 'yfinance'}), "
                f"deneme {attempt}/{attempts} başarısız. {delay:.1f}s bekleniyor..."
            )
            time.sleep(delay)
    raise last_exc
