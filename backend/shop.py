"""
shop.py
-------
Sanal ödül mağazası: haftalık görevlerden (quests.py) ve Şampiyonlar
Duvarı'ndan (hall_of_fame.py, achievements.py) kazanılan "oyun puanı"
(User.game_points) ile satın alınan KOZMETİK eşyalar. GERÇEK PARAYLA hiçbir
ilişkisi yoktur -- virtual_balance'tan tamamen ayrı, sıfırdan başlayan bir
ikinci sayaç harcanır.

Katalog kodda SABİTTİR (baskets.py/achievements.py ile aynı desen) -- ayrı
bir DB tablosu gerekmez. Yalnızca kullanıcının SAHİP OLDUĞU eşyalar
(models.UserInventory) ve o an TAKILI olan seçim (User.equipped_frame_id /
equipped_title_id) veritabanında tutulur.
"""

from typing import List, Optional, TypedDict


class MagazaEsyasi(TypedDict):
    id: str
    isim: str
    aciklama: str
    kategori: str   # 'CERCEVE' | 'UNVAN'
    maliyet: int    # oyun puanı
    deger: str      # CERCEVE için hex renk, UNVAN için gösterilecek metin


MAGAZA_ESYALARI: List[MagazaEsyasi] = [
    {"id": "cerceve-altin", "isim": "Altın Çerçeve", "aciklama": "Profilinde avatarının etrafında altın bir çerçeve.", "kategori": "CERCEVE", "maliyet": 50, "deger": "#F59E0B"},
    {"id": "cerceve-zumrut", "isim": "Zümrüt Çerçeve", "aciklama": "Profilinde avatarının etrafında zümrüt yeşili bir çerçeve.", "kategori": "CERCEVE", "maliyet": 40, "deger": "#10B981"},
    {"id": "cerceve-safir", "isim": "Safir Çerçeve", "aciklama": "Profilinde avatarının etrafında safir mavisi bir çerçeve.", "kategori": "CERCEVE", "maliyet": 75, "deger": "#38BDF8"},
    {"id": "cerceve-yakut", "isim": "Yakut Çerçeve", "aciklama": "Profilinde avatarının etrafında yakut kırmızısı bir çerçeve.", "kategori": "CERCEVE", "maliyet": 60, "deger": "#F43F5E"},
    {"id": "cerceve-ametist", "isim": "Ametist Çerçeve", "aciklama": "Profilinde avatarının etrafında ametist moru bir çerçeve.", "kategori": "CERCEVE", "maliyet": 65, "deger": "#A855F7"},
    {"id": "cerceve-gunes", "isim": "Gün Batımı Çerçeve", "aciklama": "Profilinde avatarının etrafında turuncu bir çerçeve.", "kategori": "CERCEVE", "maliyet": 55, "deger": "#FB923C"},
    {"id": "cerceve-platin", "isim": "Platin Çerçeve", "aciklama": "Profilinde avatarının etrafında gümüş-platin bir çerçeve.", "kategori": "CERCEVE", "maliyet": 90, "deger": "#CBD5E1"},
    {"id": "cerceve-elmas", "isim": "Elmas Çerçeve", "aciklama": "En nadir çerçeve — profilinde parlak camgöbeği bir çerçeve.", "kategori": "CERCEVE", "maliyet": 150, "deger": "#22D3EE"},
    {"id": "cerceve-mercan", "isim": "Mercan Çerçeve", "aciklama": "Profilinde avatarının etrafında mercan pembesi bir çerçeve.", "kategori": "CERCEVE", "maliyet": 45, "deger": "#FB7185"},
    {"id": "cerceve-lagun", "isim": "Lagün Çerçeve", "aciklama": "Profilinde avatarının etrafında turkuaz bir çerçeve.", "kategori": "CERCEVE", "maliyet": 70, "deger": "#2DD4BF"},
    {"id": "cerceve-lavanta", "isim": "Lavanta Çerçeve", "aciklama": "Profilinde avatarının etrafında açık lavanta rengi bir çerçeve.", "kategori": "CERCEVE", "maliyet": 60, "deger": "#C4B5FD"},
    {"id": "cerceve-bronz", "isim": "Bronz Çerçeve", "aciklama": "Profilinde avatarının etrafında bronz bir çerçeve.", "kategori": "CERCEVE", "maliyet": 35, "deger": "#B45309"},
    {"id": "unvan-kurt", "isim": "Borsa Kurdu", "aciklama": "Kullanıcı adının yanında 'Borsa Kurdu' unvanı.", "kategori": "UNVAN", "maliyet": 30, "deger": "Borsa Kurdu"},
    {"id": "unvan-usta", "isim": "Yatırım Ustası", "aciklama": "Kullanıcı adının yanında 'Yatırım Ustası' unvanı.", "kategori": "UNVAN", "maliyet": 60, "deger": "Yatırım Ustası"},
    {"id": "unvan-efsane", "isim": "Efsane Trader", "aciklama": "Kullanıcı adının yanında 'Efsane Trader' unvanı.", "kategori": "UNVAN", "maliyet": 100, "deger": "Efsane Trader"},
    {"id": "unvan-kahin", "isim": "Piyasa Kâhini", "aciklama": "Kullanıcı adının yanında 'Piyasa Kâhini' unvanı.", "kategori": "UNVAN", "maliyet": 70, "deger": "Piyasa Kâhini"},
    {"id": "unvan-duellocu", "isim": "Düello Ustası", "aciklama": "Kullanıcı adının yanında 'Düello Ustası' unvanı.", "kategori": "UNVAN", "maliyet": 80, "deger": "Düello Ustası"},
    {"id": "unvan-istikrarli", "isim": "Sarsılmaz El", "aciklama": "Kullanıcı adının yanında 'Sarsılmaz El' unvanı.", "kategori": "UNVAN", "maliyet": 65, "deger": "Sarsılmaz El"},
    {"id": "unvan-gozde", "isim": "Halkın Gözdesi", "aciklama": "Kullanıcı adının yanında 'Halkın Gözdesi' unvanı.", "kategori": "UNVAN", "maliyet": 120, "deger": "Halkın Gözdesi"},
    {"id": "unvan-sermaye-avcisi", "isim": "Sermaye Avcısı", "aciklama": "Kullanıcı adının yanında 'Sermaye Avcısı' unvanı.", "kategori": "UNVAN", "maliyet": 50, "deger": "Sermaye Avcısı"},
    {"id": "unvan-trend-takipcisi", "isim": "Trend Takipçisi", "aciklama": "Kullanıcı adının yanında 'Trend Takipçisi' unvanı.", "kategori": "UNVAN", "maliyet": 45, "deger": "Trend Takipçisi"},
    {"id": "unvan-gece-tacisi", "isim": "Gece Tacisi", "aciklama": "Kullanıcı adının yanında 'Gece Tacisi' unvanı.", "kategori": "UNVAN", "maliyet": 55, "deger": "Gece Tacisi"},
    {"id": "unvan-referans-elcisi", "isim": "Referans Elçisi", "aciklama": "Kullanıcı adının yanında 'Referans Elçisi' unvanı.", "kategori": "UNVAN", "maliyet": 40, "deger": "Referans Elçisi"},
]

_ESYA_HARITASI = {e["id"]: e for e in MAGAZA_ESYALARI}


def magaza_esyalari() -> List[MagazaEsyasi]:
    return MAGAZA_ESYALARI


def esya_bul(item_id: Optional[str]) -> Optional[MagazaEsyasi]:
    if not item_id:
        return None
    return _ESYA_HARITASI.get(item_id)
