"""
scorecard.py
------------
Kullanıcının işlem performans karnesi.

NEDEN: `transactions` tablosunda her satışın gerçekleşen kâr/zararı zaten
kayıtlı ama hiçbir yerde ÖZETLENMİYORDU. Kullanıcı 40 satır işlem listesine
bakıp "iyi mi gidiyorum" sorusunu cevaplayamıyor. Burada yeni hiçbir veri
çekilmez; yalnızca mevcut kayıtlar okunur.

TUTMA SÜRESİ NASIL HESAPLANIYOR (FIFO):
Bir satışın "ne kadar tutuldu" sorusunun cevabı, hangi alımın satıldığına
bağlıdır. Ortalama maliyet yöntemi bu bilgiyi vermez. Bu yüzden hisse bazında
alımlar bir kuyrukta tutulur ve satışlar en eski alımdan düşülür (FIFO).
Kısmi satışlar da doğru eşleşir: 100 adet alıp 40 satarsanız o 40'ın süresi
hesaplanır, kalan 60 kuyrukta bekler.

SINIR: Uygulama öncesi dönemden kalan pozisyonlar için alım kaydı yoktur.
Böyle bir satış eşleşemez ve tutma süresi ortalamasına KATILMAZ (sıfır gün
saymak ortalamayı aşağı çekip yanıltırdı).
"""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

import models


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def build_scorecard(db: Session, user_id: int, year: Optional[int] = None) -> dict[str, Any]:
    q = (
        db.query(models.Transaction)
        .filter_by(user_id=user_id)
        # id tiebreaker: aynı saniyedeki iki işlem aksi halde rastgele sıralanır
        # ve FIFO eşleşmesi çalıştırmadan çalıştırmaya değişirdi.
        .order_by(models.Transaction.created_at.asc(), models.Transaction.id.asc())
    )
    islemler = q.all()

    if not islemler:
        return {
            "has_data": False,
            "years": [],
            "year": year,
        }

    yillar = sorted({t.created_at.year for t in islemler if t.created_at}, reverse=True)
    hedef_yil = year if year in yillar else None

    # --- FIFO kuyrukları: tutma süresi ve hisse bazlı kırılım ----------------
    kuyruk: dict[int, deque] = defaultdict(deque)
    tutma_gunleri: list[float] = []
    hisse_pnl: dict[int, float] = defaultdict(float)
    hisse_islem: dict[int, int] = defaultdict(int)

    satis_sayisi = kazanan = kaybeden = 0
    toplam_realized = 0.0
    en_iyi = en_kotu = None
    al_hacim = sat_hacim = 0.0

    for t in islemler:
        aitYil = t.created_at.year if t.created_at else None
        kapsamda = hedef_yil is None or aitYil == hedef_yil

        adet = _f(t.quantity)
        if t.action_type == "AL":
            # Kuyruk yıl filtresinden BAĞIMSIZ doldurulur: 2025'te alınıp 2026'da
            # satılan bir pozisyonun süresi, 2026 karnesinde de doğru çıkmalı.
            kuyruk[t.stock_id].append([adet, t.created_at])
            if kapsamda:
                al_hacim += _f(t.total_amount)
                hisse_islem[t.stock_id] += 1
            continue

        # --- SAT ---
        kalan = adet
        agirlikli_gun = 0.0
        eslesen = 0.0
        while kalan > 0 and kuyruk[t.stock_id]:
            parti = kuyruk[t.stock_id][0]
            kullanilan = min(kalan, parti[0])
            if t.created_at and parti[1]:
                agirlikli_gun += (t.created_at - parti[1]).total_seconds() / 86400.0 * kullanilan
            eslesen += kullanilan
            parti[0] -= kullanilan
            kalan -= kullanilan
            if parti[0] <= 0:
                kuyruk[t.stock_id].popleft()

        if not kapsamda:
            continue

        satis_sayisi += 1
        sat_hacim += _f(t.total_amount)
        hisse_islem[t.stock_id] += 1

        # Eşleşen alım yoksa süre bilinmiyor demektir; 0 yazmak yerine atlanır.
        if eslesen > 0:
            tutma_gunleri.append(agirlikli_gun / eslesen)

        if t.realized_pnl is not None:
            pnl = _f(t.realized_pnl)
            toplam_realized += pnl
            hisse_pnl[t.stock_id] += pnl
            if pnl > 0:
                kazanan += 1
            elif pnl < 0:
                kaybeden += 1
            if en_iyi is None or pnl > en_iyi[0]:
                en_iyi = (pnl, t)
            if en_kotu is None or pnl < en_kotu[0]:
                en_kotu = (pnl, t)

    # --- Sembol çözümlemesi --------------------------------------------------
    ilgili_ids = set(hisse_pnl) | set(hisse_islem)
    semboller = {
        s.id: s.symbol
        for s in db.query(models.Stock).filter(models.Stock.id.in_(ilgili_ids)).all()
    } if ilgili_ids else {}

    def islem_ozeti(kayit) -> Optional[dict]:
        if kayit is None:
            return None
        pnl, t = kayit
        maliyet = _f(t.average_cost_at_trade)
        yuzde = ((_f(t.price) - maliyet) / maliyet * 100) if maliyet > 0 else None
        return {
            "symbol": semboller.get(t.stock_id, "?"),
            "pnl": round(pnl, 2),
            "pnl_pct": round(yuzde, 2) if yuzde is not None else None,
            "date": t.created_at,
        }

    # Sadece kâr/zararı bilinen (satışı olan) hisseler sıralanır.
    hisse_listesi = sorted(
        ({"symbol": semboller.get(sid, "?"), "pnl": round(p, 2), "trades": hisse_islem.get(sid, 0)}
         for sid, p in hisse_pnl.items() if p != 0),
        key=lambda x: x["pnl"],
        reverse=True,
    )

    kapali = kazanan + kaybeden
    return {
        "has_data": True,
        "years": yillar,
        "year": hedef_yil,
        "realized_pnl": round(toplam_realized, 2),
        "sell_count": satis_sayisi,
        "win_count": kazanan,
        "loss_count": kaybeden,
        # İsabet oranı yalnızca kâr/zararı BİLİNEN satışlar üzerinden hesaplanır.
        "win_rate": round(kazanan / kapali * 100, 1) if kapali else None,
        "avg_holding_days": round(sum(tutma_gunleri) / len(tutma_gunleri), 1) if tutma_gunleri else None,
        "matched_sells": len(tutma_gunleri),
        "best_trade": islem_ozeti(en_iyi),
        "worst_trade": islem_ozeti(en_kotu),
        "buy_volume": round(al_hacim, 2),
        "sell_volume": round(sat_hacim, 2),
        "by_stock": hisse_listesi[:5] + hisse_listesi[-5:] if len(hisse_listesi) > 10 else hisse_listesi,
    }
