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
