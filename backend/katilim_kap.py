"""
katilim_kap.py
--------------
KAP'ın "Katılım Finansı İlkeleri Bilgi Formu" bildirimlerini ayrıştırır.

NEDEN BU MODÜL VAR
------------------
Uygulamada katılım oranları bugüne kadar UYDURMAYDI. `init_db.py` içindeki
`purification_rate` değerleri ölçüldüğünde 0,4 ile 3,0 arasında neredeyse
kusursuz 0,1'lik adımlarla dizilmiş 31 farklı sayı çıktı — bu bir finansal
dağılım değil, elle yazılmış aritmetik bir dizi. 165 hissenin 111'inde ise
hiçbir değer yoktu ("BELİRSİZ"). Yani kullanıcıya rozet gösteriyorduk ama
arkasında veri yoktu.

`katilim.py` bunu bilanço oranlarından TAHMİN etmeye çalışır ve dürüst
davranıp karar vermeyi reddeder (elle küratörlü listeyle yalnızca %69 uyum).
Orada şu da açıkça yazar: dördüncü ölçüt olan "uygun olmayan gelir oranı"
yfinance'ta HİÇ YOKTUR, yalnızca KAP dipnotlarında bulunur.

Bu form tam olarak o boşluğu kapatır. SPK, payları borsada işlem gören
şirketlere bu formu KAP'a bildirme yükümlülüğü getirdi; şirket katılım
finansı ölçütlerine uygunluğunu KENDİ BEYAN EDER ve form yedi alanı da
sayısallaştırır:

    1) Esas sözleşmede aykırı faaliyet konusu var mı?        EVET/HAYIR
    2) Aykırı imtiyaz var mı?                                EVET/HAYIR
    3) Standart 1.5 / Rehber 1.D eylemleri destekliyor mu?   EVET/HAYIR
    4) Doğrudan aykırı faaliyet veya geliri var mı?          EVET/HAYIR
    5) Uygun olmayan GELİRLERİN oranı (%)                    sayı
    6) Uygun olmayan VARLIKLARIN oranı (%)                   sayı
    7) Uygun olmayan BORÇLARIN oranı (%)                     sayı

Bu, tahmin değil ŞİRKETİN RESMİ BEYANIDIR — kaynağı da kullanıcıya
gösterilebilir (her kaydın KAP bildirim bağlantısı var).

TEKNİK NOT
----------
KAP bildirim sayfası (`/tr/Bildirim/{index}`) sunucu tarafında render edilir;
oranlar HTML içinde düz metin olarak bulunur, JavaScript çalıştırmaya gerek
yoktur. Sayfa aynı içeriği İKİ KEZ barındırır: biri JSON içine kaçışlanmış
(`\\u003c`), biri düz HTML. Ayrıştırma düz HTML kopyası üzerinden yapılır.

Soru metinleri uzun ve KAP zaman zaman noktalama/boşluk değiştiriyor; bu
yüzden eşleştirme tam metinle değil, satır başındaki "N)" numarasıyla yapılır.
Numaralar mevzuatla sabittir, metin değişse bile ayrıştırma çalışmaya devam
eder.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests

from text_utils import tr_fold

KAP_BILDIRIM_URL = "https://www.kap.org.tr/tr/Bildirim/{index}"

BASLIK_ISARETI = "katilim finansi ilkeleri bilgi formu"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9",
}

# Formdaki oran satırlarının numaraları (mevzuatla sabit).
ORAN_ALANLARI = {
    5: "uygun_olmayan_gelir_pct",
    6: "uygun_olmayan_varlik_pct",
    7: "uygun_olmayan_borc_pct",
}

# Formdaki evet/hayır satırlarının numaraları.
BAYRAK_ALANLARI = {
    1: "esas_sozlesme_aykiri",
    2: "aykiri_imtiyaz",
    3: "desteklenen_aykiri_eylem",
    4: "dogrudan_aykiri_faaliyet",
}


@dataclass
class KatilimFormu:
    """Tek bir KAP Katılım Finansı İlkeleri Bilgi Formu'nun ayrıştırılmış hali."""
    disclosure_index: int
    donem: Optional[str] = None              # "2026 / 6 Aylık"
    esas_sozlesme_aykiri: Optional[bool] = None
    aykiri_imtiyaz: Optional[bool] = None
    desteklenen_aykiri_eylem: Optional[bool] = None
    dogrudan_aykiri_faaliyet: Optional[bool] = None
    uygun_olmayan_gelir_pct: Optional[float] = None
    uygun_olmayan_varlik_pct: Optional[float] = None
    uygun_olmayan_borc_pct: Optional[float] = None

    @property
    def tam_mi(self) -> bool:
        """Üç oranın da okunabildiği form 'tam' sayılır."""
        return all(
            getattr(self, alan) is not None
            for alan in ORAN_ALANLARI.values()
        )


def _etiketleri_at(parca: str) -> str:
    """HTML etiketlerini atıp boşlukları tek boşluğa indirir."""
    return " ".join(re.sub(r"<[^>]+>", " ", parca).split())


def _sayi_coz(ham: str) -> Optional[float]:
    """
    Form hücresindeki sayıyı çözer.

    TÜRKÇE SAYI TUZAĞI: KAP bu alanlarda hem "0", hem "1,25" (ondalık virgül),
    hem de "1.234,56" (binlik nokta) biçimlerini kullanabiliyor.
    `float("1.234")` patlamaz ama 1,234 döndürür — BİN KAT KÜÇÜK bir sayı.
    Bu yüzden nokta binlik ayracı olarak atılır, virgül ondalığa çevrilir
    (aynı tuzak `tr_market.tr_sayi`da da belgelenmiştir).
    """
    if ham is None:
        return None
    metin = ham.strip().replace("%", "").strip()
    if not metin or metin in {"-", "—"}:
        return None
    metin = metin.replace(".", "").replace(",", ".")
    try:
        deger = float(metin)
    except ValueError:
        return None
    # Oran alanı; negatif ya da %100'ü aşan değer form hatasıdır, kabul edilmez.
    if deger < 0 or deger > 100:
        return None
    return deger


def _evet_hayir_coz(ham: str) -> Optional[bool]:
    metin = _etiketleri_at(ham).upper()
    if "EVET" in metin:
        return True
    if "HAYIR" in metin:
        return False
    return None


def ayristir(html: str, disclosure_index: int) -> KatilimFormu:
    """
    KAP bildirim sayfasının HTML'inden Katılım Finansı formunu çıkarır.

    Eşleştirme satır numarasıyla yapılır ("5)", "6)", "7)"), soru metniyle
    değil — KAP metinleri düzenliyor ama numaralar mevzuatla sabit.
    """
    form = KatilimFormu(disclosure_index=disclosure_index)

    # Tüm tablo satırlarını gez; her satırın ilk hücresi soru/etiket,
    # sonuncusu cevaptır. Dönem bilgisi de aynı yapıda bir satırdır, bu yüzden
    # ayrı bir arama yerine aynı döngüde yakalanır (ayrı regex denendi ve
    # hücre sınırlarını doğru bulamadığı için hep boş dönüyordu).
    for satir in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        hucreler = re.findall(r"<td[^>]*>(.*?)</td>", satir, re.S)
        if len(hucreler) < 2:
            continue
        soru = _etiketleri_at(hucreler[0])

        if form.donem is None and "finansal tablo" in soru.lower() and "dönem" in soru.lower():
            aday = _etiketleri_at(hucreler[-1])
            # "2026 / 6 Aylık" gibi bir değer bekleniyor; yıl içermeyen hücre
            # etiket satırıdır, değer değil.
            if aday and re.search(r"\d{4}", aday):
                form.donem = aday
                continue

        numara_eslesme = re.match(r"^(\d+)\)", soru)
        if not numara_eslesme:
            continue
        numara = int(numara_eslesme.group(1))
        cevap_ham = hucreler[-1]

        if numara in ORAN_ALANLARI:
            # Oran satırı olduğundan emin ol: soru metninde "Oran" geçmeli.
            # Formun ilerleyen bölümlerinde de "5)" ile başlayan satırlar var.
            if "oran" not in soru.lower():
                continue
            deger = _sayi_coz(_etiketleri_at(cevap_ham))
            if deger is not None and getattr(form, ORAN_ALANLARI[numara]) is None:
                setattr(form, ORAN_ALANLARI[numara], deger)
        elif numara in BAYRAK_ALANLARI:
            deger = _evet_hayir_coz(cevap_ham)
            if deger is not None and getattr(form, BAYRAK_ALANLARI[numara]) is None:
                setattr(form, BAYRAK_ALANLARI[numara], deger)

    return form


def formu_cek(disclosure_index: int, timeout: int = 25) -> Optional[KatilimFormu]:
    """Tek bir KAP bildirimini indirip ayrıştırır; başarısızsa None."""
    url = KAP_BILDIRIM_URL.format(index=disclosure_index)
    try:
        yanit = requests.get(url, headers=HEADERS, timeout=timeout)
        yanit.raise_for_status()
    except Exception as e:
        print(f"[KatilimKAP] {disclosure_index} indirilemedi: {e}")
        return None
    return ayristir(yanit.text, disclosure_index)


def index_coz(kap_url: Optional[str]) -> Optional[int]:
    """'https://www.kap.org.tr/tr/Bildirim/1654957' -> 1654957"""
    if not kap_url:
        return None
    eslesme = re.search(r"/Bildirim/(\d+)", kap_url)
    return int(eslesme.group(1)) if eslesme else None


def kap_katilim_formlarini_senkronize_et(db, limit: Optional[int] = None,
                                         gecikme_sn: float = 1.2,
                                         zorla: bool = False,
                                         tur_basi_indirme: int = 25) -> Dict[str, int]:
    """
    Veritabanındaki "Katılım Finansı İlkeleri Bilgi Formu" KAP bildirimlerini
    gezip her hisse için en YENİ formu indirir, ayrıştırır ve `stocks`
    tablosundaki kap_katilim_* alanlarına yazar.

    NEDEN EN YENİ FORM: şirket her finansal dönemde yeni form yayımlar. Aynı
    hissenin eski formunu okumak bayat oran gösterir; bu yüzden hisse başına
    yalnızca en güncel bildirim işlenir.

    NEDEN GECİKME VAR: KAP tek tek HTML sayfası veriyor (bildirim başına ~185
    KB). Ardışık istekleri gecikmesiz atmak nazik değil; günde bir çalışan bir
    işte 0,7 saniye beklemenin maliyeti yok.
    """
    import models  # döngüsel import olmasın diye fonksiyon içinde

    bildirimler = (
        db.query(models.KapNotification)
        .filter(models.KapNotification.title.ilike("%Katılım Finansı%"))
        .filter(models.KapNotification.kap_url.isnot(None))
        .order_by(models.KapNotification.publish_date.desc())
        .all()
    )

    # Hisse başına EN YENİ bildirim (sorgu zaten tarihe göre sıralı).
    en_yeni: Dict[str, models.KapNotification] = {}
    for b in bildirimler:
        if b.symbol and b.symbol not in en_yeni:
            en_yeni[b.symbol] = b

    semboller = list(en_yeni)
    if limit:
        semboller = semboller[:limit]

    sayac = {"islenen": 0, "yazilan": 0, "atlanan": 0, "hatali": 0,
             "degismemis": 0, "ertelenen": 0}
    for sembol in semboller:
        bildirim = en_yeni[sembol]
        index = index_coz(bildirim.kap_url)
        if not index:
            sayac["atlanan"] += 1
            continue

        stock = db.query(models.Stock).filter_by(symbol=sembol).first()
        if not stock:
            # Takip etmediğimiz bir hisse; formu indirmeye gerek yok.
            sayac["atlanan"] += 1
            continue

        # DEĞİŞMEYEN FORM YENİDEN İNDİRİLMEZ. KAP bildirimleri yayımlandıktan
        # sonra değişmez (düzeltme AYRI bir bildirim olarak çıkar), bu yüzden
        # aynı bildirimi her gece yeniden indirmenin hiçbir faydası yok ama
        # maliyeti var: KAP istek sınırı uyguluyor ve ölçüldü — 36 formun
        # tamamı tek turda "429 Request Limit Exceeded" alıp ayrıştırılamadı.
        # Durağan durumda bu döngü artık sıfır istek atar.
        if not zorla and stock.kap_katilim_url == bildirim.kap_url:
            sayac["degismemis"] = sayac.get("degismemis", 0) + 1
            continue

        # TUR BAŞINA İNDİRME SINIRI. Geçmiş tarama 147 hissede form buldu;
        # hepsini tek turda indirmeye çalışmak KAP'ın istek sınırına
        # tosluyor (ölçüldü: 101 indirmeden sonra 429, ve ardından SORGU
        # API'si de kısıtlandı). Güne yayılınca birkaç turda tamamlanıyor
        # ve zaten indirilen atlandığı için her tur ilerliyor.
        if sayac["islenen"] >= tur_basi_indirme:
            sayac["ertelenen"] = sayac.get("ertelenen", 0) + 1
            continue

        sayac["islenen"] += 1
        form = formu_cek(index)
        if form is None:
            # 429 gibi bir hatada devam etmek yalnızca sınırı daha da zorlar;
            # kalan formlar bir sonraki turda alınır (kayıt kaybı olmaz,
            # çünkü değişmeyen form kontrolü sayesinde tur kısa sürüyor).
            sayac["hatali"] += 1
            print("[KatilimKAP] İndirme başarısız, tur erken sonlandırıldı "
                  "(muhtemelen istek sınırı).")
            break
        if not form.tam_mi:
            # Eksik form YAZILMAZ: yarım veri, veri yokluğundan daha kötüdür —
            # kullanıcı eksik oranı "sıfır" sanır.
            sayac["hatali"] += 1
        else:
            stock.kap_katilim_gelir_pct = form.uygun_olmayan_gelir_pct
            stock.kap_katilim_varlik_pct = form.uygun_olmayan_varlik_pct
            stock.kap_katilim_borc_pct = form.uygun_olmayan_borc_pct
            stock.kap_katilim_donem = form.donem
            stock.kap_katilim_url = bildirim.kap_url
            stock.kap_katilim_updated_at = datetime.utcnow()
            sayac["yazilan"] += 1

        if gecikme_sn:
            time.sleep(gecikme_sn)

    db.commit()
    print(f"[KatilimKAP] {sayac['islenen']} form işlendi, {sayac['yazilan']} hisse "
          f"güncellendi, {sayac['hatali']} ayrıştırılamadı, {sayac['atlanan']} atlandı, "
          f"{sayac['degismemis']} değişmemiş, {sayac['ertelenen']} sonraki tura ertelendi.")
    return sayac


def _tarih_coz(ham: Optional[str]) -> Optional[datetime]:
    """KAP'ın '20.08.2026 22:54:15' biçimini çözer."""
    if not ham:
        return None
    for bicim in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(ham.strip(), bicim)
        except ValueError:
            continue
    return None


# Üst üste bu kadar 429 alınırsa tarama durdurulur. Devam etmek yalnızca
# sınırı daha da zorlar; ölçüldü — ısrar edince KAP SORGU API'sini de
# kısıtlıyor ve tarama 147 yerine 31 form döndürür hale geliyor.
ARDISIK_HATA_SINIRI = 3


def gecmisi_tara(db, ay: int = 14, pencere_gun: int = 5,
                 sorgu_gecikme_sn: float = 1.5) -> Dict[str, int]:
    """
    KAP'ın GEÇMİŞ akışını tarayıp katılım formu bildirimlerini KENDİ
    `kap_notifications` tablomuza yazar. DETAY SAYFASI İNDİRMEZ.

    NEDEN AYRI BİR TARAMA GEREKTİ
    ----------------------------
    Günlük senkronizasyon yalnızca kendi tablomuzdaki bildirimlere bakar; o
    tablo son birkaç haftayı tutuyor. Sonuç: 165 hissenin yalnızca 36'sında
    katılım beyanı vardı. Oysa şirketler bu formu dönemsel yayımlıyor ve
    eskileri KAP'ta duruyor — geçmiş tarandığında 165 hissenin 147'sinde
    form bulundu.

    PENCERE NEDEN 5 GÜN
    -------------------
    KAP sorgusu tek istekte EN FAZLA 2000 kayıt döndürüp fazlasını SESSİZCE
    KESİYOR. Ölçüldü: aynı ay 30 günlük tek pencerede 68 form verirken, 5
    günlük dilimlere bölününce 173 form verdi — geniş pencerede formların
    %60'ı kayboluyordu.

    NEDEN DETAY İNDİRMİYOR
    ----------------------
    İlk sürüm bulduğu formların detay sayfalarını da indiriyordu ve KAP'ın
    istek sınırına toslıyordu (ölçüldü: 101 indirmeden sonra 429, ve ikinci
    denemede SORGU API'si de kısıtlanıp 147 yerine 31 form döndürdü — yani
    hırslı davranmak taramanın kendisini bozuyor).

    Artık iş bölünüyor: burası yalnızca "hangi hissenin hangi bildirimi var"
    bilgisini kendi tablomuza yazar, indirmeyi günlük senkronizasyon
    (`kap_katilim_formlarini_senkronize_et`) kendi hız sınırıyla, güne
    yayarak yapar. Zaten indirileni atladığı için her gün biraz ilerler.
    """
    import models
    from kap_client import _query_disclosures

    bugun = datetime.utcnow()
    baslangic = bugun - timedelta(days=30 * ay)
    katalog = {s.symbol for s in db.query(models.Stock).all()}
    hisse_id = {s.symbol: s.id for s in db.query(models.Stock).all()}

    # sembol -> (publish_date, disclosure_index)
    en_yeni: Dict[str, tuple] = {}
    pencere_sayisi = 0
    ardisik_hata = 0

    imlec = baslangic
    while imlec < bugun:
        bit = min(imlec + timedelta(days=pencere_gun), bugun)
        pencere_sayisi += 1
        try:
            kayitlar = _query_disclosures(imlec, bit)
            ardisik_hata = 0
        except Exception as e:
            ardisik_hata += 1
            print(f"[KatilimKAP] {imlec.date()}..{bit.date()} sorgulanamadı: {e}")
            if ardisik_hata >= ARDISIK_HATA_SINIRI:
                print(f"[KatilimKAP] {ardisik_hata} ardışık hata — tarama durduruldu. "
                      "İstek sınırı dolmuş olabilir, bir sonraki turda denenecek.")
                break
            imlec = bit
            time.sleep(sorgu_gecikme_sn * 2)
            continue

        for kayit in kayitlar:
            baslik = kayit.get("summary") or kayit.get("subject") or ""
            if BASLIK_ISARETI not in tr_fold(baslik):
                continue
            sembol = (kayit.get("stockCodes") or "").strip().upper()
            index = kayit.get("disclosureIndex")
            if not sembol or sembol not in katalog or not index:
                continue
            tarih = _tarih_coz(kayit.get("publishDate")) or datetime.min
            mevcut = en_yeni.get(sembol)
            if mevcut is None or tarih > mevcut[0]:
                en_yeni[sembol] = (tarih, index)

        imlec = bit
        if sorgu_gecikme_sn:
            time.sleep(sorgu_gecikme_sn)

    sayac = {"pencere": pencere_sayisi, "bulunan": len(en_yeni), "eklenen": 0, "zaten_var": 0}

    for sembol, (tarih, index) in sorted(en_yeni.items()):
        url = KAP_BILDIRIM_URL.format(index=index)
        var = (
            db.query(models.KapNotification)
            .filter_by(symbol=sembol, kap_url=url)
            .first()
        )
        if var:
            sayac["zaten_var"] += 1
            continue
        db.add(models.KapNotification(
            stock_id=hisse_id.get(sembol),
            symbol=sembol,
            title="Katılım Finansı İlkeleri Bilgi Formu",
            kap_url=url,
            publish_date=tarih if tarih != datetime.min else bugun,
        ))
        sayac["eklenen"] += 1

    db.commit()
    print("[KatilimKAP] Geçmiş tarama: {pencere} pencere, {bulunan} hissede form, "
          "{eklenen} yeni bildirim kaydedildi, {zaten_var} zaten vardı.".format(**sayac))
    return sayac
