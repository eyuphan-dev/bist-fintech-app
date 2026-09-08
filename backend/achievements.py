"""
achievements.py
----------------
Genel başarım/rozet sistemi -- katılım rozetlerinden (KatilimBadge, tek bir
uygunluk durumunu gösterir) FARKLI: kullanıcının platform genelindeki
aktiflik ve başarısını ödüllendiren, birikimli bir oyunlaştırma katmanı.

TASARIM İLKESİ -- BİR ROZET KAZANILDIKTAN SONRA KALICIDIR: koşul daha sonra
geçerliliğini yitirse bile (örn. pozisyon satılırsa "Çeşitlendirme Ustası"
geri alınmaz). Bu, yerleşik oyunlaştırma sistemlerinin (Steam başarımları,
Duolingo rozetleri vb.) standart davranışıdır -- kullanıcıyı "kazandığımı
kaybettim" hayal kırıklığından korur ve veritabanında `UserAchievement`
satırı olarak KALICI tutulur (her istekte yeniden hesaplanmaz).

Kontrol fonksiyonları veritabanına DOĞRUDAN erişmez -- main.py zaten fiyat/
portföy hesaplama mantığına sahip olduğu için (döngüsel import riski
olmadan), main.py bir `Baglam` sözlüğü hazırlayıp buraya geçirir. Böylece
bu modül saf/test edilebilir kalır.
"""

from typing import Callable, List, TypedDict


class Baglam(TypedDict):
    islem_sayisi: int
    sektor_sayisi: int
    getiri_pct: float
    tam_katilim_uyumlu: bool
    temettu_hisse_sayisi: int
    hesap_yasi_gun: int
    karli_satis_sayisi: int
    buyuk_karli_satis_var: bool
    favori_sayisi: int
    yorum_sayisi: int
    oy_sayisi: int
    bekleyen_emir_var_mi: bool
    davet_sayisi: int
    gece_islemi_var_mi: bool


class BasarimTanimi(TypedDict):
    id: str
    isim: str
    aciklama: str
    kontrol: Callable[[Baglam], bool]


BASARIM_TANIMLARI: List[BasarimTanimi] = [
    {
        "id": "ilk-adim",
        "isim": "İlk Adım",
        "aciklama": "İlk alım/satım işlemini tamamladın.",
        "kontrol": lambda b: b["islem_sayisi"] >= 1,
    },
    {
        "id": "aktif-yatirimci",
        "isim": "Aktif Yatırımcı",
        "aciklama": "10 alım/satım işlemi tamamladın.",
        "kontrol": lambda b: b["islem_sayisi"] >= 10,
    },
    {
        "id": "deneyimli-trader",
        "isim": "Deneyimli Trader",
        "aciklama": "50 alım/satım işlemi tamamladın.",
        "kontrol": lambda b: b["islem_sayisi"] >= 50,
    },
    {
        "id": "cesitlendirme-ustasi",
        "isim": "Çeşitlendirme Ustası",
        "aciklama": "Portföyünde 5 farklı sektörden hisse bulunduruyorsun.",
        "kontrol": lambda b: b["sektor_sayisi"] >= 5,
    },
    {
        "id": "kar-makinesi",
        "isim": "Kâr Makinesi",
        "aciklama": "Toplam getirin %20'yi geçti.",
        "kontrol": lambda b: b["getiri_pct"] >= 20,
    },
    {
        "id": "katilim-sadigi",
        "isim": "Katılım Sadığı",
        "aciklama": "Portföyünün tamamı (en az 3 pozisyon) katılım uygun hisselerden oluşuyor.",
        "kontrol": lambda b: b["tam_katilim_uyumlu"],
    },
    {
        "id": "temettu-avcisi",
        "isim": "Temettü Avcısı",
        "aciklama": "Temettü ödeyen 3 farklı hisseye sahipsin.",
        "kontrol": lambda b: b["temettu_hisse_sayisi"] >= 3,
    },
    {
        "id": "sadik-uye",
        "isim": "Sadık Üye",
        "aciklama": "Hesabın 30 günden daha eski.",
        "kontrol": lambda b: b["hesap_yasi_gun"] >= 30,
    },
    {
        "id": "ilk-kar",
        "isim": "İlk Kâr",
        "aciklama": "İlk kez kârla bir pozisyon kapattın.",
        "kontrol": lambda b: b["karli_satis_sayisi"] >= 1,
    },
    {
        "id": "keskin-nisanci",
        "isim": "Keskin Nişancı",
        "aciklama": "Bir satışta maliyetine göre %50 veya üzeri kâr elde ettin.",
        "kontrol": lambda b: b["buyuk_karli_satis_var"],
    },
    {
        "id": "takipci",
        "isim": "Takipçi",
        "aciklama": "İzleme listende en az 10 hisse bulunduruyorsun.",
        "kontrol": lambda b: b["favori_sayisi"] >= 10,
    },
    {
        "id": "sosyal-yatirimci",
        "isim": "Sosyal Yatırımcı",
        "aciklama": "En az 5 hisseye yorum yaptın.",
        "kontrol": lambda b: b["yorum_sayisi"] >= 5,
    },
    {
        "id": "kahin-adayi",
        "isim": "Kâhin Adayı",
        "aciklama": "En az 10 hissede yükseliş/düşüş yönü tahmini yaptın.",
        "kontrol": lambda b: b["oy_sayisi"] >= 10,
    },
    {
        "id": "stratejist",
        "isim": "Stratejist",
        "aciklama": "İlk limit, zamanlı veya stop emrini oluşturdun.",
        "kontrol": lambda b: b["bekleyen_emir_var_mi"],
    },
    {
        "id": "topluluk-elcisi",
        "isim": "Topluluk Elçisi",
        "aciklama": "Referans kodunla en az 1 arkadaşını davet ettin.",
        "kontrol": lambda b: b["davet_sayisi"] >= 1,
    },
    {
        "id": "gece-kusu",
        "isim": "Gece Kuşu",
        "aciklama": "Gece yarısı ile 05:00 arasında bir işlemin gerçekleşti.",
        "kontrol": lambda b: b["gece_islemi_var_mi"],
    },
]

_TANIM_HARITASI = {t["id"]: t for t in BASARIM_TANIMLARI}


def basarim_tanimlari() -> List[BasarimTanimi]:
    return BASARIM_TANIMLARI


def kazanilanlari_hesapla(baglam: Baglam) -> List[str]:
    """Verilen bağlamda koşulu sağlanan TÜM başarımların id listesini döner."""
    return [t["id"] for t in BASARIM_TANIMLARI if t["kontrol"](baglam)]
