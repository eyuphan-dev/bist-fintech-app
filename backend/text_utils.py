"""
text_utils.py
-------------
Türkçe metinlerde güvenli küçültme.

BULUNAN HATA: Python'ın yerleşik str.lower() metodu Türkçe büyük "İ" harfini
ASCII "i" değil, "i" + görünmez bir birleştirici nokta (U+0307, COMBINING DOT
ABOVE) üretir. Yani:

    "İçeriden".lower() == "i̇çeriden"   (2. karakter U+0307, ekrana yansımaz)
    "içeriden" in "İçeriden".lower()   -> False

Bu, KAP başlığı gibi büyük harfle başlayan her Türkçe cümlede anahtar kelime
eşleşmesini SESSİZCE kırar. `insider_client.py`de ölçülerek bulundu: "İçeriden
Öğrenenler İşlemi" başlıklı gerçek bir KAP bildirimi, anahtar kelime listesinde
"içeriden öğrenen" olmasına rağmen hiç eşleşmiyordu — 165 hisselik katalogda
içeriden öğrenen verisinin neredeyse hiç birikmemesinin bir nedeni de buydu.

Aynı desen `sentiment.py`de de var: "İyi hisse." gibi büyük İ ile başlayan bir
topluluk yorumu, "iyi" pozitif kelimesiyle asla eşleşmiyordu.

ÇÖZÜM: küçültmeden önce "İ"yi elle ASCII "i"ye çevir. (Doğru Türkçe küçültme
"İ"->"i", "I"->"ı" şeklindedir, ama burada amaç dilbilgisel doğruluk değil,
ASCII anahtar kelime eşleşmesinin bozulmaması; bu yüzden yalnızca "İ" eşlenir.)
"""


def tr_lower(text: str) -> str:
    """Türkçe metni, anahtar kelime eşleştirmesi için güvenli şekilde küçültür."""
    if not text:
        return text
    return text.replace("İ", "i").lower()


# Türkçe "noktasız I" sorunu, tr_lower'ın çözdüğünün AYNASIDIR ve TEFAS fon
# adlarında ölçülerek bulundu. TEFAS fon adlarını TAMAMI BÜYÜK HARF döndürür:
#
#     "PARDUS PORTFÖY KISA VADELİ KATILIM SERBEST FONU"
#
# Burada "KATILIM".lower() == "katilim" (ASCII i) olur, ama insanın yazdığı
# anahtar kelime "katılım"dır (noktasız ı). İkisi eşleşmez. Ters yönde de aynı
# şey olur: "Katılım".lower() == "katılım", ASCII "katilim" ile eşleşmez.
#
# Bu yüzden tefas_client.py'deki KATILIM_KEYWORDS listesi HİÇBİR ZAMAN
# eşleşmiyordu; anahtar kelimenin hem "katılım" hem "katilim" varyantını
# elle yazmak da her yeni kelimede aynı tuzağı kurmak demekti.
#
# tr_fold, karşılaştırmanın İKİ TARAFINA da uygulanır ve tüm i/ı ailesini tek
# bir ASCII "i"ye indirger. Sonuç Türkçe olarak okunaklı değildir — okunaklı
# olması da amaç değil; amaç anahtar kelime eşleşmesinin sessizce kırılmaması.

_KATLAMA = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ş": "s", "ş": "s",
    "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u",
    "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
})


def tr_fold(text: str) -> str:
    """Anahtar kelime eşleştirmesi için Türkçe metni ASCII'ye katlar.

    Karşılaştırmanın hem metin hem anahtar kelime tarafına uygulanmalıdır:
        tr_fold("KATILIM SERBEST FONU")  -> "katilim serbest fonu"
        tr_fold("katılım")               -> "katilim"          (eşleşir)
    """
    if not text:
        return text
    return text.translate(_KATLAMA).lower()
