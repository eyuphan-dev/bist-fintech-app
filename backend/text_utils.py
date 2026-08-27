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
