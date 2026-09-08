"""
duels.py
--------
1v1 meydan okuma (düello): iki kullanıcı arasında, KABUL ANINDAKİ portföy
değerleriyle başlayan sabit 7 günlük bir yarış. Kazanan, dönem içindeki
GETİRİ YÜZDESİ daha yüksek olan taraftır -- mutlak TL değeri değil, farklı
bakiyeyle başlayan iki kullanıcı arasında adil karşılaştırma budur (ana
liderlik tablosuyla aynı ilke).
"""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

import models

DUEL_SURESI_GUN = 7


def portfoy_degeri(db: Session, user_id: int) -> float:
    """Bir kullanıcının GÜNCEL manuel portföy değeri (nakit + pozisyonlar)."""
    user = db.query(models.User).filter_by(id=user_id).first()
    if not user:
        return 0.0
    toplam = float(user.virtual_balance)
    pozisyonlar = db.query(models.Portfolio).filter_by(user_id=user_id, is_bot_portfolio=False).all()
    if not pozisyonlar:
        return toplam

    son_fiyatlar = {}
    for stock_id in {p.stock_id for p in pozisyonlar}:
        son = (
            db.query(models.StockPrice.price)
            .filter(models.StockPrice.stock_id == stock_id)
            .order_by(models.StockPrice.recorded_at.desc())
            .first()
        )
        if son:
            son_fiyatlar[stock_id] = float(son[0])

    for p in pozisyonlar:
        fiyat = son_fiyatlar.get(p.stock_id, float(p.average_cost))
        toplam += float(p.quantity) * fiyat
    return toplam


def getiri_pct(baseline: float, guncel: float) -> float:
    if not baseline:
        return 0.0
    return ((guncel - baseline) / baseline) * 100


def resolve_bitenler(db: Session) -> int:
    """Süresi dolmuş ACTIVE düelloları sonuçlandırır. Kaç düellonun sonuçlandığını döner."""
    simdi = datetime.utcnow()
    bitenler = (
        db.query(models.Duel)
        .filter(models.Duel.status == "ACTIVE", models.Duel.ends_at <= simdi)
        .all()
    )
    for d in bitenler:
        challenger_getiri = getiri_pct(float(d.challenger_baseline or 0), portfoy_degeri(db, d.challenger_id))
        opponent_getiri = getiri_pct(float(d.opponent_baseline or 0), portfoy_degeri(db, d.opponent_id))

        d.status = "COMPLETED"
        d.resolved_at = simdi
        if challenger_getiri > opponent_getiri:
            d.winner_id = d.challenger_id
        elif opponent_getiri > challenger_getiri:
            d.winner_id = d.opponent_id
        # Eşitlikte winner_id None kalır (berabere) -- duel_wins kimseye eklenmez.

        if d.winner_id:
            kazanan = db.query(models.User).filter_by(id=d.winner_id).first()
            if kazanan:
                kazanan.duel_wins = (kazanan.duel_wins or 0) + 1

    if bitenler:
        db.commit()
    return len(bitenler)
