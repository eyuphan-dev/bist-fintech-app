"""
quests.py
---------
Haftalık görevler: her hafta Pazartesi'den itibaren sıfırdan değerlendirilen,
tamamlanınca bir kerelik "oyun puanı" (User.game_points) kazandıran küçük
hedefler.

achievements.py'DEN FARKI: başarımlar KALICI ve tek seferliktir (bir kez
kazanılan geri alınmaz); görevler HER HAFTA yeniden değerlendirilir ve hafta
başına yalnızca BİR KEZ tamamlanabilir (bkz. models.UserQuestCompletion).

Kontrol fonksiyonları veritabanına doğrudan erişmez -- main.py bağlamı
hazırlayıp buraya geçirir (achievements.py ile aynı desen).
"""

from typing import Callable, List, TypedDict


class GorevBaglami(TypedDict):
    sektor_sayisi_bu_hafta: int
    islem_sayisi_bu_hafta: int
    farkli_hisse_alinan_bu_hafta: int
    favori_eklenen_bu_hafta: int
    yorum_sayisi_bu_hafta: int
    uzun_tutulan_pozisyon_var_mi: bool


class GorevTanimi(TypedDict):
    id: str
    isim: str
    aciklama: str
    puan: int
    kontrol: Callable[[GorevBaglami], bool]


GOREV_TANIMLARI: List[GorevTanimi] = [
    {
        "id": "cesitli-alim",
        "isim": "Çeşitli Alım",
        "aciklama": "Bu hafta en az 3 farklı sektörden hisse al.",
        "puan": 15,
        "kontrol": lambda b: b["sektor_sayisi_bu_hafta"] >= 3,
    },
    {
        "id": "aktif-hafta",
        "isim": "Aktif Hafta",
        "aciklama": "Bu hafta en az 5 alım/satım işlemi yap.",
        "puan": 10,
        "kontrol": lambda b: b["islem_sayisi_bu_hafta"] >= 5,
    },
    {
        "id": "genis-yelpaze",
        "isim": "Geniş Yelpaze",
        "aciklama": "Bu hafta 3 farklı hisseden alım yap.",
        "puan": 10,
        "kontrol": lambda b: b["farkli_hisse_alinan_bu_hafta"] >= 3,
    },
    {
        "id": "izleme-listesi-genislet",
        "isim": "İzleme Listeni Genişlet",
        "aciklama": "Bu hafta izleme listene en az 3 hisse ekle.",
        "puan": 10,
        "kontrol": lambda b: b["favori_eklenen_bu_hafta"] >= 3,
    },
    {
        "id": "topluluga-katil",
        "isim": "Topluluğa Katıl",
        "aciklama": "Bu hafta en az 1 hisseye yorum yap.",
        "puan": 5,
        "kontrol": lambda b: b["yorum_sayisi_bu_hafta"] >= 1,
    },
    {
        "id": "sabirli-yatirimci",
        "isim": "Sabırlı Yatırımcı",
        "aciklama": "En az bir pozisyonu 5 günden uzun süredir elinde tutuyorsun.",
        "puan": 10,
        "kontrol": lambda b: b["uzun_tutulan_pozisyon_var_mi"],
    },
]


def gorev_tanimlari() -> List[GorevTanimi]:
    return GOREV_TANIMLARI


def tamamlananlari_hesapla(baglam: GorevBaglami) -> List[str]:
    """Verilen bağlamda koşulu sağlanan TÜM görevlerin id listesini döner."""
    return [t["id"] for t in GOREV_TANIMLARI if t["kontrol"](baglam)]
