"""
market_hours.py
---------------
BİST (Borsa İstanbul) seans saatleri kontrol modülü.
Redis veya harici bir servis kullanmadan, sadece Python'un datetime kütüphanesi
ile anlık zaman kontrolü yaparak borsa açık/kapalı durumunu belirler.

Borsa Saatleri:
  Hafta içi (Pazartesi–Cuma): 10:00 – 18:15 (Türkiye saati / Europe/Istanbul)
  Hafta sonu (Cumartesi, Pazar): KAPALI
  Resmi tatiller: Manuel olarak BIST_HOLIDAYS listesine eklenir.

Cron Job Önerileri (Sunucu seviyesinde):
  Fiyat Güncelleme : */5 10-18 * * 1-5   (hafta içi, 10–18 arası her 5 dk)
  Bot Çalıştırma   : */10 10-18 * * 1-5  (hafta içi, 10–18 arası her 10 dk)
  Log Temizleme    : 0 3 * * 0            (her pazar sabahı 03:00)
"""

from datetime import datetime, date, time
from datetime import date as date_type
from typing import Tuple
import pytz

# -------------------------------------------------------------------
# Sabit Tanımlar
# -------------------------------------------------------------------
TR_TZ = pytz.timezone("Europe/Istanbul")

# Seans başlangıç ve bitiş saatleri
MARKET_OPEN_TIME  = time(10, 0, 0)   # 10:00:00
MARKET_CLOSE_TIME = time(18, 15, 0)  # 18:15:00

# Manuel olarak tanımlanan BİST resmi tatil günleri (YYYY-MM-DD)
# Her yıl güncellenmesi gerekir. SPK takvimi: https://www.borsaistanbul.com/
BIST_HOLIDAYS: set[date] = {
    # 2025 tatilleri
    date(2025, 1, 1),   # Yılbaşı
    date(2025, 3, 30),  # Ramazan Bayramı Arife
    date(2025, 3, 31),  # Ramazan Bayramı 1. Gün
    date(2025, 4, 1),   # Ramazan Bayramı 2. Gün
    date(2025, 4, 2),   # Ramazan Bayramı 3. Gün
    date(2025, 4, 23),  # Ulusal Egemenlik ve Çocuk Bayramı
    date(2025, 5, 1),   # Emek ve Dayanışma Günü
    date(2025, 5, 19),  # Atatürk'ü Anma, Gençlik ve Spor Bayramı
    date(2025, 6, 5),   # Kurban Bayramı Arife
    date(2025, 6, 6),   # Kurban Bayramı 1. Gün
    date(2025, 6, 7),   # Kurban Bayramı 2. Gün
    date(2025, 6, 8),   # Kurban Bayramı 3. Gün
    date(2025, 6, 9),   # Kurban Bayramı 4. Gün
    date(2025, 7, 15),  # Demokrasi ve Millî Birlik Günü
    date(2025, 8, 30),  # Zafer Bayramı
    date(2025, 10, 29), # Cumhuriyet Bayramı
    # 2026 tatilleri
    date(2026, 1, 1),   # Yılbaşı
    date(2026, 3, 19),  # Ramazan Bayramı Arife
    date(2026, 3, 20),  # Ramazan Bayramı 1. Gün
    date(2026, 3, 21),  # Ramazan Bayramı 2. Gün
    date(2026, 3, 22),  # Ramazan Bayramı 3. Gün
    date(2026, 4, 23),  # Ulusal Egemenlik ve Çocuk Bayramı
    date(2026, 5, 1),   # Emek ve Dayanışma Günü
    date(2026, 5, 19),  # Atatürk'ü Anma, Gençlik ve Spor Bayramı
    date(2026, 5, 26),  # Kurban Bayramı Arife
    date(2026, 5, 27),  # Kurban Bayramı 1. Gün
    date(2026, 5, 28),  # Kurban Bayramı 2. Gün
    date(2026, 5, 29),  # Kurban Bayramı 3. Gün
    date(2026, 5, 30),  # Kurban Bayramı 4. Gün
    date(2026, 7, 15),  # Demokrasi ve Millî Birlik Günü
    date(2026, 8, 30),  # Zafer Bayramı
    date(2026, 10, 29), # Cumhuriyet Bayramı
}


# -------------------------------------------------------------------
# Ana Kontrol Fonksiyonu
# -------------------------------------------------------------------
def is_market_open(force_open: bool = False) -> Tuple[bool, str]:
    """
    BİST'in şu an açık olup olmadığını kontrol eder.

    Kontrol sırası:
      1. Geliştirici modu zorlaması (force_open=True)
      2. Hafta sonu kontrolü (Cumartesi/Pazar → kapalı)
      3. Resmi tatil kontrolü
      4. Saat 10:00–18:15 aralığı kontrolü

    Args:
        force_open: True ise test/geliştirme ortamında saatleri bypass eder.

    Returns:
        Tuple[bool, str]: (açık_mı, sebep_mesajı)

    Kullanım:
        open_flag, reason = is_market_open()
        if not open_flag:
            print(f"Borsa kapalı: {reason}")
            return
    """
    if force_open:
        return True, "Geliştirici modu: Borsa saatleri bypass edildi."

    now_tr: datetime = datetime.now(TR_TZ)
    today: date = now_tr.date()
    current_time: time = now_tr.time()
    weekday: int = now_tr.weekday()  # 0=Pazartesi … 6=Pazar

    # ── Kural 1: Hafta sonu ──────────────────────────────────────────
    if weekday >= 5:  # 5=Cumartesi, 6=Pazar
        day_names = {5: "Cumartesi", 6: "Pazar"}
        return False, f"Hafta sonu ({day_names[weekday]}): BİST kapalı."

    # ── Kural 2: Resmi tatil ─────────────────────────────────────────
    if today in BIST_HOLIDAYS:
        return False, f"Resmi tatil ({today.strftime('%d.%m.%Y')}): BİST kapalı."

    # ── Kural 3: Seans saatleri ──────────────────────────────────────
    if current_time < MARKET_OPEN_TIME:
        opens_in = _minutes_until(now_tr, MARKET_OPEN_TIME)
        return False, f"Seans henüz açılmadı. Açılışa {opens_in} dakika kaldı (10:00)."

    if current_time > MARKET_CLOSE_TIME:
        return False, f"Seans kapandı (18:15). Sonraki iş günü 10:00'da açılacak."

    # ── Borsa Açık ───────────────────────────────────────────────────
    closes_in = _minutes_until(now_tr, MARKET_CLOSE_TIME)
    return True, f"BİST açık. Kapanışa {closes_in} dakika kaldı (18:15)."


def get_market_status_dict() -> dict:
    """
    API endpoint'leri için borsa durumunu dict formatında döner.

    Returns:
        {
            "is_open": bool,
            "reason": str,
            "current_time_tr": "HH:MM",
            "market_open": "10:00",
            "market_close": "18:15",
            "weekday": "Salı"
        }
    """
    is_open, reason = is_market_open()
    now_tr = datetime.now(TR_TZ)
    weekday_names = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

    return {
        "is_open": is_open,
        "reason": reason,
        "current_time_tr": now_tr.strftime("%H:%M"),
        "market_open": "10:00",
        "market_close": "18:15",
        "weekday": weekday_names[now_tr.weekday()],
    }


# -------------------------------------------------------------------
# Yardımcı Fonksiyonlar
# -------------------------------------------------------------------
def _minutes_until(now: datetime, target: time) -> int:
    """Verilen saat hedefine kaç dakika kaldığını hesaplar."""
    now_tr = now.astimezone(TR_TZ)
    target_dt = now_tr.replace(
        hour=target.hour,
        minute=target.minute,
        second=0,
        microsecond=0
    )
    delta = target_dt - now_tr
    return max(0, int(delta.total_seconds() // 60))


def market_guard(func):
    """
    Dekoratör: Yalnızca BİST seans saatlerinde çalışması gereken
    fonksiyonlar için kullanılır. Borsa kapalıysa fonksiyon çalıştırılmaz
    ve bir uyarı logu yazılır.

    Kullanım:
        @market_guard
        def my_job():
            # sadece borsa saatlerinde çalışır
            ...
    """
    def wrapper(*args, **kwargs):
        open_flag, reason = is_market_open()
        if not open_flag:
            print(f"[market_guard] İşlem iptal edildi: {reason}")
            return None
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def bugun_tr() -> "date_type":
    """
    Türkiye saatine göre BUGÜNÜN tarihi.

    NEDEN GEREKLİ: sunucu UTC'de çalışıyor. TSİ 00:00–03:00 arasında UTC hâlâ
    bir önceki gündedir, yani `date.today()` DÜNÜ döndürür. Piyasa günü sınırı
    bu tarihe göre belirlenen her yerde bu, bir gün bayat sonuç demektir:

      • Pivot seviyeleri kapanmış son seansı "bugün" sayıp eler (ölçüldü:
        TSİ 01:54'te üretim 26 Ağustos barını kullanırken TSİ'deki yerel
        makine 27 Ağustos barını kullanıyordu — aynı kod, farklı sonuç).
      • Günlük % değişimin referans kapanışı bir gün eskiye kayar.
      • Bilanço takvimi dünkü açıklamayı "yaklaşan" olarak gösterir.

    Piyasa Türkiye'de olduğu için gün sınırı da Türkiye saatiyle belirlenir.
    Kayan pencerelerde (son 30 gün, son 1 yıl) bir günlük fark önemsizdir;
    orada `date.today()` bırakılabilir.
    """
    return datetime.now(TR_TZ).date()
