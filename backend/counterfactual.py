"""
counterfactual.py
-------------------
"Sen olmasan ne olurdu?" karnesi.

Rakiplerin ve bizim de yapamadığımız/yapmadığımız bir şey: kullanıcıya kendi
işlem kararının GERÇEK maliyetini üç somut alternatifle kıyaslayarak göstermek.

    A) Hiç işlem yapmasaydı  — sermaye nakitte kalırdı.
    B) Sermayeyi ilk işlem gününde toptan BIST 100'e yatırıp dokunmasaydı.
    C) Sermayeyi hesap açılışından bugüne AYLIK EŞİT PARÇALAR halinde
       BIST 100'e yatırsaydı (DCA — Dolar Maliyet Ortalaması'nın TL karşılığı).

NEDEN BU ÜÇÜ VE BAŞKASI DEĞİL: hepsi `index_history` (XU100 günlük kapanış)
ve kullanıcının zaten var olan `baseline_value` / `created_at` alanlarından
tam olarak hesaplanabilir. Uydurma bir varsayım (örn. "ortalama yatırımcı
%X kazanır" gibi bir literatür sayısı) KULLANILMAZ — `katilim.py`deki yer
tutucu oran hatasından ders alındı (bkz. projem.md §12).

DÜRÜSTLÜK SINIRI: bu üç senaryo de komisyonsuzdur (gerçek bir endeks fonu
komisyonu ~binde birkaç olur, ihmal edilebilir düzeyde) ve BIST 100'ün kendisi
alınabilir bir enstrüman değildir (ETF/endeks fonu üzerinden alınır, küçük bir
takip farkı olur). Bu basitleştirmeler yanıtta AÇIKÇA belirtilir.
"""

from datetime import date, timedelta
from typing import List, Optional, TypedDict

from sqlalchemy.orm import Session

import models


class CounterfactualScenario(TypedDict):
    key: str
    label: str
    final_value: float
    return_pct: float


class CounterfactualResult(TypedDict):
    actual_value: float
    actual_return_pct: float
    baseline_capital: float
    scenarios: List[CounterfactualScenario]
    note: str


def _index_closes(db: Session, start: date, end: date) -> List[tuple]:
    """XU100 günlük kapanışları, tarih artan sırada. Boşsa boş liste döner."""
    rows = (
        db.query(models.IndexHistory)
        .filter(
            models.IndexHistory.symbol == "XU100",
            models.IndexHistory.trade_date >= start - timedelta(days=10),
            models.IndexHistory.trade_date <= end,
        )
        .order_by(models.IndexHistory.trade_date.asc())
        .all()
    )
    return [(r.trade_date, float(r.close)) for r in rows if float(r.close) > 0]


def _closest_close_on_or_before(pairs: List[tuple], target: date) -> Optional[float]:
    """target tarihinden ÖNCEKİ veya O GÜNKÜ en yakın kapanış. İLERİYE BAKMAZ."""
    best = None
    for d, close in pairs:
        if d <= target:
            best = close
        else:
            break
    return best


def compute_counterfactual(
    db: Session,
    user: models.User,
    actual_value: float,
) -> Optional[CounterfactualResult]:
    """
    None döner: hesaplamak için yeterli veri yoksa (yeni hesap, endeks verisi
    yok, hiç işlem yapılmamış). Sessizce yanlış/uydurma bir sayı göstermek
    yerine özelliği tümüyle gizlemek daha doğru.
    """
    baseline = float(user.baseline_value or 100000.0)
    if baseline <= 0:
        return None

    ilk_islem = (
        db.query(models.Transaction)
        .filter_by(user_id=user.id, action_type="AL")
        .order_by(models.Transaction.created_at.asc())
        .first()
    )
    hesap_acilis = user.created_at.date() if user.created_at else date.today()
    baslangic = ilk_islem.created_at.date() if ilk_islem else hesap_acilis
    bugun = date.today()

    if baslangic >= bugun:
        return None  # hesap bugün açıldı, kıyaslayacak zaman yok

    pairs = _index_closes(db, baslangic, bugun)
    if len(pairs) < 2:
        return None  # endeks verisi henüz yetersiz

    baslangic_kapanis = _closest_close_on_or_before(pairs, baslangic)
    bugun_kapanis = pairs[-1][1]
    if not baslangic_kapanis or baslangic_kapanis <= 0:
        return None

    senaryolar: List[CounterfactualScenario] = []

    # A) Hiç işlem yapmasaydı — sermaye nakitte, hiç büyümez/küçülmez.
    senaryolar.append(CounterfactualScenario(
        key="cash", label="Hiç işlem yapmasaydın (nakit)",
        final_value=round(baseline, 2), return_pct=0.0,
    ))

    # B) Tek seferde BIST 100'e yatırıp dokunmasaydı.
    b_deger = baseline * (bugun_kapanis / baslangic_kapanis)
    senaryolar.append(CounterfactualScenario(
        key="lump_sum_xu100", label="Sermayeni ilk işlem gününde BIST 100'e yatırıp dokunmasaydın",
        final_value=round(b_deger, 2), return_pct=round((b_deger - baseline) / baseline * 100, 2),
    ))

    # C) Aylık eşit parçalarla DCA — hesap açılışından bugüne kadar her ayın
    # 1'ine (veya en yakın işlem gününe) eşit tutar yatırılmış gibi.
    aylar: List[date] = []
    imlec = date(baslangic.year, baslangic.month, 1)
    while imlec <= bugun:
        aylar.append(imlec)
        yil, ay = imlec.year, imlec.month + 1
        if ay > 12:
            yil, ay = yil + 1, 1
        imlec = date(yil, ay, 1)

    if aylar:
        aylik_tutar = baseline / len(aylar)
        c_deger = 0.0
        for ay_baslangic in aylar:
            kapanis = _closest_close_on_or_before(pairs, ay_baslangic) or baslangic_kapanis
            if kapanis > 0:
                c_deger += aylik_tutar * (bugun_kapanis / kapanis)
        senaryolar.append(CounterfactualScenario(
            key="dca_xu100", label="Sermayeni her ay eşit parçalarla BIST 100'e yatırsaydın",
            final_value=round(c_deger, 2), return_pct=round((c_deger - baseline) / baseline * 100, 2),
        ))

    return CounterfactualResult(
        actual_value=round(actual_value, 2),
        actual_return_pct=round((actual_value - baseline) / baseline * 100, 2),
        baseline_capital=round(baseline, 2),
        scenarios=senaryolar,
        note="Senaryolar komisyonsuzdur ve BIST 100'ün doğrudan alınabildiği "
             "varsayılır (gerçekte endeks fonu/ETF üzerinden, küçük bir takip "
             "farkıyla alınır). Yatırım tavsiyesi değildir.",
    )
