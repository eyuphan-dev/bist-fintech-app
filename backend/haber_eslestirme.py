"""
haber_eslestirme.py
-------------------
Türkçe haber metinlerini BİST hisseleriyle eşleştirir.

NEDEN GEREKLİ
-------------
Ölçüldü: Yahoo Finance'ın BİST haber kapsamı çok zayıf. Üretimde 165 hissenin
yalnızca 29'unda haber vardı ve en yenisi 5 gün eskiydi; 136 hisse sayfası
haber bölümü boş açılıyordu. Türkçe RSS kaynakları (Foreks, AA, Dünya, TRT,
BloombergHT vb.) tek turda ~320 haber veriyor ve içerik gerçekten BİST odaklı
("Sarkuysan'dan bedelsiz sermaye artırımı kararı").

Ama RSS bize haberin HANGİ HİSSEYE ait olduğunu söylemez; bunu metinden
çıkarmak gerekir. Buradaki tüm mesele o eşleştirmenin YANLIŞ EŞLEŞME
ÜRETMEMESİDİR: kullanıcı ASELS sayfasında Aselsan'la ilgisi olmayan bir haber
görürse, boş bir haber bölümünden daha kötü olur.

EŞLEŞTİRME NASIL YAPILIYOR
--------------------------
İki tür anahtar üretilir:

  1. SEMBOL  — "THYAO", "SARKY". Kelime sınırıyla aranır. Çok yüksek kesinlik;
     Türkçe finans haberleri sembolü sıkça yazar.

  2. MARKA   — şirket unvanından hukuki ve jenerik ekler atılarak elde edilen
     ayırt edici kısım ("Sarkuysan Elektrolitik Bakır Sanayi ve Ticaret A.Ş."
     -> "sarkuysan").

Eşleştirme `text_utils.tr_fold` üzerinden yapılır; haber metni "ŞİŞE" de
yazabilir "Şişe" de, ikisi de eşleşmeli (bkz. text_utils).

YANLIŞ EŞLEŞMEYE KARŞI ÜÇ KORUMA (hepsi ölçülerek doğrulandı)
-------------------------------------------------------------
  a) SEMBOL BÜYÜK HARF ARANIR. Sembolü küçük harfe katlayıp aramak sessiz
     çakışma üretiyordu: SISE <- "şişe ağırlığı", KONYA <- "Ankara-Konya".
     Borsa kodu haber metninde her zaman büyük harfle yazılır.

  b) JENERİK İLK KELİMEDE İKİ KELİME ŞARTI. "girisim" (GESAN), "hareket"
     (HRKET), "celebi" (CLEBI) tek başına yanlış eşleşme üretti; iki kelimeye
     çıkarılınca ("girisim elektrik") sıfıra indi.

  c) KELİME SINIRI: alt dize değil, kelime sınırı aranır.

ÖLÇÜM (320 haberlik gerçek RSS derlemi)
    ilk hali           : 11 eşleşme, %36 kesinlik
    sembol büyük harf  : 11 eşleşme, %64 kesinlik
    + iki kelime şartı :  7 eşleşme, %100 kesinlik   <- yürürlükteki hali

İsabetin düşük olması beklenen bir sonuçtur: ekonomi haberlerinin çoğu
belirli bir BİST hissesiyle ilgili değildir. Eşleşmeyen haberler kaybolmaz,
genel piyasa haberleri akışında (`market_news`) gösterilir.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

from text_utils import tr_fold

# Unvan sonundaki hukuki ve yapısal ekler. Markanın parçası değildirler.
# Sondan başlayarak tekrar tekrar atılırlar.
KUYRUK_EKLERI = {
    "as", "a", "s", "tas", "t", "anonim", "sirketi", "sirket",
    "sanayi", "sanayii", "san", "ticaret", "tic", "ve", "ile",
    "holding", "holdings", "grup", "grubu", "group",
    "yatirim", "yatirimlar", "yatirimlari", "ortakligi", "ortakliklari",
    "isletmeleri", "isletme", "isletmecilik",
    "gayrimenkul", "gayirmenkul", "gyo",
    "magazacilik", "magazalar", "pazarlama", "dagitim", "dis",
    "uretim", "urunleri", "hizmetleri", "hizmet",
    "elektrik", "elektronik", "otomotiv",
    "fabrikalari", "fabrika", "endustri", "endustriyel",
}

# TEK KELİMELİK marka anahtarı olarak KULLANILAMAYACAK kelimeler.
#
# Bunlar günlük Türkçede ya da coğrafi ad olarak geçer; tek başına marka
# sayılırlarsa alakasız haberi hisseye bağlarlar. Gerçek haber derlemi (320
# haber) üzerinde ölçülerek bulundu — her biri yanlış eşleşme ÜRETTİ:
#
#   "global"  <- "global finansal teknoloji şirketi Fasset"      (GLYHO)
#   "halk"    <- Halkbank haberleri                              (HLGYO)
#   "konya"   <- "Ankara-Konya Yüksek Hızlı Tren Hattı"          (KONYA)
#   "turkiye" <- haberlerin %13,4'ünde geçiyor (ölçüldü)
#   "turk"    <- haberlerin %3,1'inde geçiyor  (ölçüldü)
#
# Bu kelimeler ÇOK KELİMELİK marka içinde serbesttir: "konya cimento"
# güvenlidir, yalnız başına "konya" değildir.
# Ölçülen yanlış eşleşmeler (320 haberlik gerçek derlem):
#   "girisim" <- "aktif girişim sayısı 4 milyon..."         (GESAN)
#   "hareket" <- "Hidropar Hareket Kontrol Teknolojileri"   (HRKET, başka şirket)
#   "celebi"  <- "İlham Çelebi'ye ait paylar"               (CLEBI, kişi soyadı)
#   "global"  <- "global finansal teknoloji şirketi"        (GLYHO)
#   "halk"    <- Halkbank haberleri                         (HLGYO)
#   "konya"   <- "Ankara-Konya Yüksek Hızlı Tren"           (KONYA)
TEK_KELIME_YASAKLI = {
    # Coğrafi adlar
    "turkiye", "turk", "anadolu", "ege", "marmara", "akdeniz", "karadeniz",
    "ankara", "izmir", "bursa", "adana", "konya", "kuzey", "guney", "bati",
    "dogu", "asya", "avrupa", "dunya",
    # Günlük kelimeler
    "global", "halk", "kent", "arena", "merkez", "dogal", "genel", "birlik",
    "ulusal", "girisim", "hareket", "hedef", "guven", "ozel", "milli",
    "yeni", "buyuk", "mega", "atlas", "gunes", "deniz", "orman", "toprak",
    "safir", "umit", "beyaz", "kirmizi", "yesil", "mavi",
    # Sektör adları
    "sanayi", "ticaret", "yatirim", "enerji", "banka", "bankasi", "sigorta",
    "teknoloji", "iletisim", "havacilik", "insaat", "tekstil", "celik",
    "demir", "bakir", "altin", "gumus",
    # Kişi soyadı olarak da geçenler
    "celebi", "dogan", "koc", "sabanci", "yildiz", "guler", "ozak", "dogus",
    # Kısa/jenerik
    "bor", "iz", "bin", "dof", "aksa", "kordsa", "deva", "kaplamin",
}

# Marka anahtarı için asgari harf sayısı (kelime sınırıyla aransa bile
# 3 harfli markalar gürültü üretiyor).
ASGARI_MARKA_UZUNLUGU = 4

# Sembol için asgari uzunluk. BİST sembolleri 4-5 harflidir.
ASGARI_SEMBOL_UZUNLUGU = 4


def marka_cikar(company_name: str) -> Optional[str]:
    """
    Şirket unvanından ayırt edici markayı çıkarır.

    "Sarkuysan Elektrolitik Bakır Sanayi ve Ticaret A.Ş." -> "sarkuysan"
    "Türk Hava Yolları A.O."                              -> "turk hava yollari"
    "Çelik Halat ve Tel Sanayii A.Ş."                     -> "celik halat ve tel"

    Sondan kuyruk ekleri atılır; baştan kesilmez. Baştan kesmek "BİM Birleşik
    Mağazalar" gibi kısa markaları yok ediyordu (ölçüldü: 165 hissenin 39'unda
    marka boş çıkıyordu, aralarında THYAO, GARAN, SISE, KCHOL vardı).
    """
    if not company_name:
        return None
    katlanmis = tr_fold(company_name).replace(".", " ")
    kelimeler = [k for k in re.split(r"[^a-z0-9]+", katlanmis) if k]

    # Sondan kuyruk eklerini at.
    while kelimeler and kelimeler[-1] in KUYRUK_EKLERI:
        kelimeler.pop()

    if not kelimeler:
        return None
    marka = " ".join(kelimeler)
    # Sadece harf sayısına bak (boşluklar sayılmaz).
    if len(marka.replace(" ", "")) < ASGARI_MARKA_UZUNLUGU:
        return None
    return marka


def _kelime_sinirli_desen(anahtar: str) -> re.Pattern:
    """Anahtarı kelime sınırıyla arayan derlenmiş desen."""
    return re.compile(r"(?<![a-z0-9])" + re.escape(anahtar) + r"(?![a-z0-9])")


class HaberEslestirici:
    """
    Hisse kataloğundan anahtarları bir kez üretip birçok haberi hızlıca
    eşleştirir. Desenler önceden derlenir; 320 haber x 165 hisse her turda
    yeniden derlenirse gereksiz maliyet çıkar.
    """

    def __init__(self, hisseler: Iterable[Tuple[str, str]]):
        """hisseler: (symbol, company_name) ikilileri."""
        # Sembol desenleri HAM metinde, BÜYÜK HARF duyarlı aranır (aşağıya bak).
        self.sembol_desenleri: Dict[str, re.Pattern] = {}
        # Marka desenleri katlanmış metinde aranır.
        self.marka_desenleri: Dict[str, List[re.Pattern]] = {}
        self.markalar: Dict[str, str] = {}

        for symbol, company_name in hisseler:
            if not symbol:
                continue
            sembol = symbol.strip().upper()
            if len(sembol) >= ASGARI_SEMBOL_UZUNLUGU:
                # SEMBOL NEDEN BÜYÜK HARF ARANIYOR: sembolü katlayıp küçük
                # harfte aramak sessiz çakışma üretiyordu (ölçüldü):
                #   SISE  <- "şişe ağırlığını yüzde 20 azaltacak"  (şişe = cam kap)
                #   KONYA <- "Ankara-Konya Yüksek Hızlı Tren"      (şehir adı)
                # Borsa kodu haber metninde HER ZAMAN büyük harfle yazılır,
                # günlük kelime yazılmaz. Bu tek kural iki hatayı da kapatır.
                self.sembol_desenleri[sembol] = re.compile(
                    r"(?<![A-Za-zÇĞİÖŞÜçğıöşü0-9])" + re.escape(sembol)
                    + r"(?![A-Za-zÇĞİÖŞÜçğıöşü0-9])"
                )

            marka = marka_cikar(company_name)
            if not marka:
                continue
            self.markalar[sembol] = marka
            anahtar = self._marka_anahtari(marka)
            if anahtar:
                self.marka_desenleri[sembol] = [_kelime_sinirli_desen(anahtar)]

    @staticmethod
    def _marka_anahtari(marka: str) -> Optional[str]:
        """
        Markadan aranacak TEK anahtarı seçer.

        TAM UNVAN KULLANILMAZ, çünkü haber şirketi kısa adıyla anar:
        "Sarkuysan'dan bedelsiz..." metni "sarkuysan elektrolitik bakir"
        anahtarıyla eşleşmez.

        KURAL (gerçek derlem üzerinde ölçülerek belirlendi):
          • İlk kelime ayırt ediciyse (>= 5 harf, yasak listesinde değil)
            tek başına kullanılır  -> "astor", "sarkuysan"
          • İlk kelime jenerikse İKİ kelime şartı gelir
            -> "girisim elektrik", "celebi hava", "hareket proje"
          • İki kelime de yoksa marka hiç kullanılmaz; o hisse yalnızca
            sembolüyle eşleşir.

        Bu kural yanlış eşleşmeyi 4'ten 0'a indirdi (11 eşleşmede %64 kesinlik
        -> 7 eşleşmede %100 kesinlik). İsabet düştü ama doğru olmayan haberi
        hisse sayfasında göstermek, haberi hiç göstermemekten kötüdür.
        """
        tokenlar = marka.split()
        ilk = tokenlar[0]
        if ilk not in TEK_KELIME_YASAKLI and len(ilk) >= 5:
            return ilk
        if len(tokenlar) >= 2:
            return " ".join(tokenlar[:2])
        return None

    def eslestir(self, metin: str) -> Dict[str, str]:
        """
        Metinde geçen hisseleri döner: {symbol: "sembol" | "marka"}.

        Sembol eşleşmesi marka eşleşmesini ezer (daha kesindir).
        """
        if not metin:
            return {}
        katlanmis = tr_fold(metin)
        bulunan: Dict[str, str] = {}

        for sembol, desen in self.sembol_desenleri.items():
            if desen.search(metin):  # HAM metin — büyük harf duyarlı
                bulunan[sembol] = "sembol"

        for sembol, desenler in self.marka_desenleri.items():
            if sembol in bulunan:
                continue
            if any(d.search(katlanmis) for d in desenler):
                bulunan[sembol] = "marka"

        return bulunan
