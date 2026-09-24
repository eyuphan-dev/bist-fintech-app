"""
marketplace.py
--------------
Sepet pazaryeri yardımcıları: kullanıcıların yayınladığı hisse+ağırlık
sepetlerinin GETİRİSİ ve oyun puanı kuralları.

Getiri, sepet yayınlandığı andaki fiyatlardan (entry_price) itibaren hesaplanır
ve yayın sonrası değiştirilemez -- güvenilirlik buradan gelir. Her şey SANAL
bakiye ile çalışır; gerçek para/aracı kurum bağlantısı yoktur.
"""

from typing import Iterable, Optional, Tuple

MAX_AKTIF_SEPET = 5          # kullanıcı başına yayında olabilecek sepet
KOPYA_PUANI = 5              # başkası kopyalayınca yayıncıya (tekil kullanıcı başına)
KOPYA_PUAN_TAVANI = 100      # bir sepetten kazanılabilecek toplam puan


def sepet_getirisi(kalemler: Iterable[Tuple[float, float, Optional[float]]]) -> Optional[float]:
    """
    kalemler: (agirlik_pct, giris_fiyati, guncel_fiyat|None).
    Güncel fiyatı olmayan kalem 0% sayılır (uydurma getiri yok). Hiç kalem
    yoksa None.
    """
    toplam = 0.0
    var = False
    for agirlik, giris, guncel in kalemler:
        var = True
        if not giris or giris <= 0 or not guncel or guncel <= 0:
            continue
        toplam += (agirlik / 100.0) * ((guncel / giris) - 1.0) * 100.0
    return round(toplam, 2) if var else None


def kopya_puani(onceki_toplam_puan: int) -> int:
    """Tavana kadar KOPYA_PUANI; tavan aşılırsa 0."""
    return max(0, min(KOPYA_PUANI, KOPYA_PUAN_TAVANI - onceki_toplam_puan))
