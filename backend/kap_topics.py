"""
kap_topics.py
-------------
KAP bildirim başlıklarını konuya göre sınıflandırır.

NEDEN AYRI BİR MODÜL: eskiden bu mantık `main.py` içinde tek satırlık bir
anahtar kelime listesiydi ve ÖLÇÜLDÜĞÜNDE HİÇ EŞLEŞMİYORDU. Üretimdeki 675
bildirimin tamamı tarandı; "önemli pay sahibi" ucu 0 kayıt döndürüyordu, çünkü
listedeki kelimeler ("pay sahip", "oy hak", "hakim ortak") KAP'ın gerçekte
kullandığı başlıklardan hiçbiriyle eşleşmiyordu. KAP'ın gerçek başlıkları:

    "Pay Alım Satım Bildirimi"
    "Payların Geri Alınmasına İlişkin Bildirim"
    "25.08.2026 Tarihli Pay Geri Alım İşlemleri"
    "Erdemoğlu Holding A.Ş. Pay Alım İşlemleri"
    "Zorunlu Pay Alım Teklifi Fiyatına İlişkin Güncelleme"
    "Ana Ortaklar Pay Satış Biilgi Formları"      (yazım hatası KAP'ta böyle)
    "Temel Ticaret ve Yatırım A.Ş.'den Ford Otosan paylarının alımı"

DIŞLAMA NEDEN ZORUNLU: "pay" alt dizesi KAP'ta çok yüklü bir kelime. Sadece
dahil-etme listesiyle çalışırsak akış tamamen alakasız kayıtla dolar:

    "THYAO.E işlem sırasında Pay Bazında Devre Kesici..."  -> volatilite tedbiri
    "Kâr Payı Avansı Dağıtmama Kararı"                     -> temettü, sahiplik değil
    "Pay Piyasasında Volatilite Bazlı Tedbir Sistemi"      -> piyasa geneli duyuru
    "LOGO Paylarında Likidite Sağlayıcılığı..."            -> piyasa yapıcılığı
    "Bedelsiz Sermaye Artırımına İlişkin..."               -> sermaye artırımı

Üretim verisinde tek başına "devre kesici" başlıkları 60'tan fazla kayıt; onlar
elenmezse akışın neredeyse tamamı gürültü olurdu.

Eşleştirme `text_utils.tr_lower` ile yapılır — KAP başlıkları büyük "İ" içerir
ve Python'ın `str.lower()` metodu onu ASCII "i" değil, "i" + U+0307 üretir
(bkz. text_utils.py).
"""

from typing import Optional

from text_utils import tr_lower

# Sahiplik yapısında gerçek bir değişikliğe işaret eden başlık kalıpları.
# Hepsi üretimdeki gerçek KAP başlıklarından çıkarıldı, tahminle yazılmadı.
MAJOR_HOLDER_INCLUDE = (
    "pay alım satım bildirimi",
    "pay alım işlemleri",
    "pay alım teklifi",
    "paylarının alımı",
    "pay satış",
    "pay geri alım",
    "payların geri alınması",
    "pay devri",
    "pay sahipliğinde değişiklik",
    "ortaklık yapısı",
    "hakim ortak",
    "hâkim ortak",
    "oy hakkı",
    "oy hak",
    "yönetim kontrolü",
    "fazla pay alan",
)

# Yukarıdakilerden birine takılsa bile bunlardan biri geçiyorsa kayıt elenir.
# Sıra önemli: dışlama her zaman dahil etmeyi ezer.
MAJOR_HOLDER_EXCLUDE = (
    "devre kesici",
    "volatilite bazlı tedbir",
    "likidite sağlayıcı",
    "işlem yasağı",
    "kar payı",
    "kâr payı",
    "sermaye artırım",
    "sermaye artım",
    "kaydileştirilmeyen",
    "tazmin merkezi",
    "piyasa yapıcı",
)


def is_major_holder_news(title: Optional[str]) -> bool:
    """
    Başlık, önemli pay sahipliği hareketi bildiriyorsa True döner.

    Dışlama listesi dahil etme listesini ezer; "Pay Geri Alım" içeren ama aynı
    zamanda "Devre Kesici" olan bir başlık elenir.
    """
    if not title:
        return False
    t = tr_lower(title)
    if any(kotu in t for kotu in MAJOR_HOLDER_EXCLUDE):
        return False
    return any(iyi in t for iyi in MAJOR_HOLDER_INCLUDE)
