"""
hall_of_fame.py
----------------
Haftalık/aylık dönem kapandığında (Pazartesi sabahı / ayın ilk günü) bir
önceki dönemin GETİRİ, İSTİKRAR ve AKTİFLİK kategorilerinde ilk 3'ünü
`hall_of_fame` tablosuna KALICI olarak yazar (bkz. models.HallOfFameEntry).

scheduler.py içinden HER GÜN bir kez çağrılır; idempotent'tir -- aynı
dönem/kategori için satır zaten varsa atlanır (bkz. UniqueConstraint),
bu yüzden günde birden fazla çalışsa da sorun çıkmaz.

NEDEN HER GÜN KONTROL: hafta sonu bitişi (Pazartesi) her zaman hafta içi
düşer ama AY bitişi hafta sonuna denk gelebilir (ör. ayın son günü Cumartesi
olabilir) -- yalnızca hafta içi çalışan bir işe bağlarsak o ay hiç
arşivlenmezdi.
"""

from datetime import date, timedelta
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

import models
from leaderboard_categories import istikrar_siralamasi, aktiflik_siralamasi, getiri_siralamasi

TOP_N = 3


def _hafta_bilgisi(dun: date) -> Optional[Tuple[str, date, date]]:
    """`dun` bir Pazar günüyse (bir önceki hafta bitmiş demektir) (etiket, başlangıç, bitiş) döner."""
    if dun.weekday() != 6:  # Python: 0=Pazartesi ... 6=Pazar
        return None
    hafta_sonu = dun
    hafta_basi = hafta_sonu - timedelta(days=6)
    iso_yil, iso_hafta, _ = hafta_basi.isocalendar()
    return f"{iso_yil}-H{iso_hafta:02d}", hafta_basi, hafta_sonu


def _ay_bilgisi(dun: date) -> Optional[Tuple[str, date, date]]:
    """`dun` ayın son günüyse (bir önceki ay bitmiş demektir) (etiket, başlangıç, bitiş) döner."""
    yarin = dun + timedelta(days=1)
    if yarin.day != 1:
        return None
    ay_basi = dun.replace(day=1)
    return f"{dun.year}-{dun.month:02d}", ay_basi, dun


def _arsivle_kategori(
    db: Session, period: str, period_label: str, period_end: date,
    kategori: str, siralama: List[Tuple[int, float]],
) -> int:
    zaten_var = db.query(models.HallOfFameEntry.id).filter_by(
        period=period, period_label=period_label, category=kategori
    ).first()
    if zaten_var:
        return 0
    en_iyiler = sorted(siralama, key=lambda x: x[1], reverse=True)[:TOP_N]
    for i, (uid, deger) in enumerate(en_iyiler, start=1):
        db.add(models.HallOfFameEntry(
            period=period, period_label=period_label, period_end_date=period_end,
            category=kategori, rank=i, user_id=uid, metric_value=round(deger, 4),
        ))
    return len(en_iyiler)


def arsivle(db: Session) -> int:
    """Bugün itibarıyla kapanmış bir hafta/ay varsa arşivler. Kaç satır eklendiğini döner."""
    bugun = date.today()
    dun = bugun - timedelta(days=1)
    toplam_eklenen = 0

    for periyot, bilgi_fn in (("weekly", _hafta_bilgisi), ("monthly", _ay_bilgisi)):
        bilgi = bilgi_fn(dun)
        if not bilgi:
            continue
        label, baslangic, bitis = bilgi

        user_ids = [u[0] for u in db.query(models.User.id).filter_by(is_bot=False).all()]
        if not user_ids:
            continue

        toplam_eklenen += _arsivle_kategori(
            db, periyot, label, bitis, "GETIRI",
            getiri_siralamasi(db, user_ids, baslangic, bitis),
        )
        toplam_eklenen += _arsivle_kategori(
            db, periyot, label, bitis, "ISTIKRAR",
            [(uid, oran) for uid, oran, _ in istikrar_siralamasi(db, user_ids, baslangic, bitis)],
        )
        toplam_eklenen += _arsivle_kategori(
            db, periyot, label, bitis, "AKTIFLIK",
            [(uid, float(adet)) for uid, adet in aktiflik_siralamasi(db, user_ids, baslangic, bitis)],
        )
        db.commit()

    return toplam_eklenen
