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
]

_TANIM_HARITASI = {t["id"]: t for t in BASARIM_TANIMLARI}


def basarim_tanimlari() -> List[BasarimTanimi]:
    return BASARIM_TANIMLARI


def kazanilanlari_hesapla(baglam: Baglam) -> List[str]:
    """Verilen bağlamda koşulu sağlanan TÜM başarımların id listesini döner."""
    return [t["id"] for t in BASARIM_TANIMLARI if t["kontrol"](baglam)]
