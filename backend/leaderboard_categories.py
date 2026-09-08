"""
leaderboard_categories.py
--------------------------
Liderlik tablosunun "getiri" DIŞINDAKİ ek kategorileri: istikrar (getiri/risk
oranı), aktiflik (işlem sayısı) ve kâhin (yön tahmini isabet oranı).

Kapsam bilinçli olarak dar tutuldu: bu üç kategori yalnızca GERÇEK
kullanıcıları kapsar (kişisel botlar hariç) -- botların günlük işlem/oy
verisi bu kategorilerle tutarlı karşılaştırılamazdı. Ana "getiri" kategorisi
(main.py get_leaderboard) botları içermeye devam eder, bunlar EK sekmelerdir.

Aynı fonksiyonlar hem CANLI liderlik ucu (main.py) hem de haftalık/aylık
arşivleme işi (hall_of_fame.py) tarafından kullanılır -- tek fark period_end
parametresinin "bugün" mü yoksa "geçen haftanın/ayın son günü" mü olduğudur.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

import models


def istikrar_siralamasi(
    db: Session, user_ids: List[int], period_start: Optional[date], period_end: date
) -> List[Tuple[int, float, int]]:
    """
    Her kullanıcı için getiri/risk oranını (günlük değer değişimlerinin
    ortalaması / standart sapması) döner: [(user_id, oran, veri_noktasi), ...].

    Yıllıklandırma YAPILMAZ: sabit pozitif bir çarpan sıralamayı değiştirmez,
    burada tek amaç bağıl karşılaştırmadır (mutlak Sharpe değeri değil).
    En az 4 kayıt (3 günlük getiri) ve std > 0 şartı aranır -- tek günlük
    veya hiç oynamayan (std=0) bir seri "sonsuz" oran üretip listeyi bozardı.
    """
    q = db.query(models.UserPerformanceHistory).filter(
        models.UserPerformanceHistory.user_id.in_(user_ids),
        models.UserPerformanceHistory.recorded_date <= period_end,
    )
    if period_start is not None:
        q = q.filter(models.UserPerformanceHistory.recorded_date >= period_start)
    satirlar = q.order_by(
        models.UserPerformanceHistory.user_id, models.UserPerformanceHistory.recorded_date
    ).all()

    kullanici_serileri: Dict[int, List[float]] = {}
    for s in satirlar:
        kullanici_serileri.setdefault(s.user_id, []).append(float(s.total_portfolio_value))

    sonuc: List[Tuple[int, float, int]] = []
    for uid, seri in kullanici_serileri.items():
        if len(seri) < 4:
            continue
        getiriler = [
            (seri[i] - seri[i - 1]) / seri[i - 1]
            for i in range(1, len(seri)) if seri[i - 1] > 0
        ]
        if len(getiriler) < 3:
            continue
        ortalama = sum(getiriler) / len(getiriler)
        varyans = sum((g - ortalama) ** 2 for g in getiriler) / len(getiriler)
        std = varyans ** 0.5
        if std <= 0:
            continue
        sonuc.append((uid, ortalama / std, len(getiriler)))
    return sonuc


def aktiflik_siralamasi(
    db: Session, user_ids: List[int], period_start: Optional[date], period_end: date
) -> List[Tuple[int, int]]:
    """Her kullanıcının dönem içinde gerçekleşmiş (AL+SAT) işlem sayısı."""
    q = db.query(
        models.Transaction.user_id, func.count(models.Transaction.id)
    ).filter(models.Transaction.user_id.in_(user_ids))
    if period_start is not None:
        q = q.filter(func.date(models.Transaction.created_at) >= period_start)
    q = q.filter(func.date(models.Transaction.created_at) <= period_end)
    return q.group_by(models.Transaction.user_id).all()


def kahin_siralamasi(
    db: Session, min_gun: int = 3, max_gun: int = 45, min_oy: int = 3
) -> List[Tuple[int, float, int]]:
    """
    Her kullanıcının yön tahmini (StockVote) isabet oranı (%): [(user_id, oran, toplam_oy), ...].

    Yalnızca en az `min_gun` gün önce verilmiş (sonuçlanmaya vakti olmuş) ve
    en fazla `max_gun` gün önce verilmiş (güncelliğini korumuş) oylar
    değerlendirilir. En az `min_oy` çözümlenmiş oyu olmayan kullanıcı
    listelenmez (tek oyla "%100 isabet" göstermek yanıltıcı olurdu).

    Bilinçli basit/pragmatik: kullanıcı başına ek sorgular içerir (N+1) --
    uygulamanın hedef ölçeği (10-15 kullanıcı, günde birkaç oy) için bu kabul
    edilebilir; toplu optimizasyon şimdilik gereksiz karmaşıklık olurdu.
    Dönemsel (haftalık/aylık) sınırlama bilerek YAPILMAZ: bir tahminin doğru
    çıkıp çıkmadığı ne zaman verildiğine değil, ne zaman SONUÇLANDIĞINA bağlı
    olduğu için bu kategori periyot sekmelerinden bağımsız, kayan bir
    pencerede (`min_gun`-`max_gun` gün önce) çalışır.
    """
    simdi = datetime.utcnow()
    alt_sinir = simdi - timedelta(days=max_gun)
    ust_sinir = simdi - timedelta(days=min_gun)
    oylar = (
        db.query(models.StockVote)
        .filter(models.StockVote.created_at >= alt_sinir, models.StockVote.created_at <= ust_sinir)
        .all()
    )
    if not oylar:
        return []

    stock_ids = list({o.stock_id for o in oylar})
    guncel_fiyat_haritasi: Dict[int, float] = {}
    for sid in stock_ids:
        son = (
            db.query(models.StockPrice.price)
            .filter(models.StockPrice.stock_id == sid)
            .order_by(models.StockPrice.recorded_at.desc())
            .first()
        )
        if son:
            guncel_fiyat_haritasi[sid] = float(son[0])

    istatistik: Dict[int, List[int]] = {}
    for oy in oylar:
        guncel = guncel_fiyat_haritasi.get(oy.stock_id)
        if not guncel:
            continue
        oy_ani = (
            db.query(models.StockPrice.price)
            .filter(models.StockPrice.stock_id == oy.stock_id, models.StockPrice.recorded_at <= oy.created_at)
            .order_by(models.StockPrice.recorded_at.desc())
            .first()
        )
        if not oy_ani:
            continue
        eski = float(oy_ani[0])
        if eski <= 0:
            continue
        dogru = (oy.direction == "UP" and guncel > eski) or (oy.direction == "DOWN" and guncel < eski)
        kayit = istatistik.setdefault(oy.user_id, [0, 0])
        kayit[1] += 1
        if dogru:
            kayit[0] += 1

    sonuc: List[Tuple[int, float, int]] = []
    for uid, (dogru_sayisi, toplam) in istatistik.items():
        if toplam < min_oy:
            continue
        sonuc.append((uid, (dogru_sayisi / toplam) * 100, toplam))
    return sonuc


def getiri_siralamasi(
    db: Session, user_ids: List[int], period_start: Optional[date], period_end: date
) -> List[Tuple[int, float]]:
    """
    Dönem başı/sonu portföy değerinden getiri yüzdesi -- yalnızca GERÇEK
    kullanıcılar (bkz. modül başlığı). Canlı "tüm zamanlar" liderlik tablosu
    (main.py get_leaderboard, period='all') botları da içerdiği ve farklı bir
    baseline mantığı kullandığı için BU fonksiyonu kullanmaz; bu yalnızca
    Şampiyonlar Duvarı arşivlemesi ve İSTİKRAR/AKTİFLİK ile tutarlı bir
    "dönem bazlı getiri" sekmesi sunmak için vardır.
    """
    q = db.query(models.UserPerformanceHistory).filter(
        models.UserPerformanceHistory.user_id.in_(user_ids),
        models.UserPerformanceHistory.recorded_date <= period_end,
    )
    if period_start is not None:
        q = q.filter(models.UserPerformanceHistory.recorded_date >= period_start)
    satirlar = q.order_by(
        models.UserPerformanceHistory.user_id, models.UserPerformanceHistory.recorded_date
    ).all()

    ilk: Dict[int, float] = {}
    son: Dict[int, float] = {}
    for s in satirlar:
        deger = float(s.total_portfolio_value)
        if s.user_id not in ilk:
            ilk[s.user_id] = deger
        son[s.user_id] = deger

    sonuc: List[Tuple[int, float]] = []
    for uid, baslangic in ilk.items():
        if baslangic <= 0:
            continue
        bitis = son.get(uid, baslangic)
        sonuc.append((uid, ((bitis - baslangic) / baslangic) * 100))
    return sonuc


# --- Kariyer rütbesi ---------------------------------------------------------

RUTBE_PUANLARI = {1: 3, 2: 2, 3: 1}

RUTBE_ESIKLERI = [
    (10, "Elmas"),
    (6, "Altın"),
    (3, "Gümüş"),
    (1, "Bronz"),
    (0, "Yeni Başlayan"),
]


def rutbe_hesapla(kariyer_puani: int) -> str:
    for esik, isim in RUTBE_ESIKLERI:
        if kariyer_puani >= esik:
            return isim
    return "Yeni Başlayan"
