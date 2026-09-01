"""
constants.py
------------
Birden fazla modül tarafından paylaşılan sabitler. Tek başına önemsiz
görünseler de her iki yerde ayrı tanımlanıp zamanla birbirinden sapmalarını
önlemek için tek bir yerden import edilirler.
"""

# Sermaye artırımı/bölünme gibi kurumsal işlemler referans fiyatı tek seferde
# katlarca değiştirebiliyor (bkz. main.py:get_stocks, notifications.py). BİST'in
# normal devre kesici kuralları bunu asla üretmeyeceğinden, %50'yi aşan
# gün-içi/günlük sıçramalar güvenilmez kabul edilip None (bilgi yok) döndürülür.
EXTREME_CHANGE_GUARD_PCT = 50.0


# ---------------------------------------------------------------------------
# Islem komisyonu
# ---------------------------------------------------------------------------
# BIST'te araci kurum komisyonu tipik olarak binde 0.2 civarindadir ve ALIMDA
# VE SATIMDA AYRI AYRI alinir.
#
# NEDEN BURADA: bu deger uzun sure YALNIZCA backtest.py'de tanimliydi. Sonuc
# tersine donmustu -- backtest komisyon kesiyor, kullanicinin gercek AL/SAT
# islemi kesmiyordu, yani kullanicinin kendi islemleri stratejilerden
# sistematik olarak KARLI gorunuyordu. Uygulamanin ogretmeye calistigi seyin
# tam tersi. Artik uc islem yolu da (main.py /api/trade, orders.py bekleyen
# emir, bot.py) ayni sabiti ve ayni yardimci fonksiyonlari kullaniyor
# (bkz. transactions.py: alim_maliyeti / satim_geliri).
KOMISYON_ORANI_PCT = 0.02


# ---------------------------------------------------------------------------
# Grafik/gosterge zaman araligi kodlari
# ---------------------------------------------------------------------------
# "1D" haric (o, gun ici stock_prices tablosundan gelir). Hem /history hem
# /indicator-series ayni araliklari kullanir; tek yerden tanimlanir ki ikisi
# zamanla birbirinden sapmasin.
HISTORY_RANGE_DAYS = {"1W": 7, "1M": 31, "1Y": 366, "5Y": 1827}
