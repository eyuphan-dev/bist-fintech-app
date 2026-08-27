"""
Kullanıcı işlem geçmişi kaydı (Transaction) için ortak yardımcı.

Neden ayrı modül: kayıt hem anlık işlemlerde (main.py -> /api/trade) hem de
bekleyen emirlerin gerçekleşmesinde (orders.py -> _execute_single_order)
yazılıyor. Aynı mantığı iki yere kopyalarsak zamanla ayrışır (örneğin
gerçekleşen K/Z formülü bir tarafta güncellenip diğerinde unutulur).
main.py <-> orders.py arasında dairesel import riski olmasın diye bu modül
ikisinden de bağımsız durur; yalnızca models'a bağlıdır.
"""

from typing import Optional, Tuple

from sqlalchemy.orm import Session

import models
from constants import KOMISYON_ORANI_PCT


def komisyon_hesapla(quantity: float, price: float) -> float:
    """İşlem tutarı üzerinden komisyon. Alımda ve satımda ayrı ayrı alınır."""
    return round(quantity * price * KOMISYON_ORANI_PCT / 100.0, 2)


def alim_maliyeti(quantity: float, price: float) -> Tuple[float, float, float]:
    """
    (brüt_tutar, komisyon, bakiyeden_düşülecek_toplam)

    Alımda komisyon maliyeti ARTIRIR: bakiyeden brüt tutar + komisyon düşülür.
    Komisyon ortalama maliyete de dahil edilir (bkz. `alim_maliyeti` çağrıldığı
    yerler) — gerçek muhasebe böyle çalışır ve kâr/zarar ancak bu şekilde
    dürüst olur. Aksi halde komisyon hiçbir yerde görünmeden kaybolurdu.
    """
    brut = round(quantity * price, 2)
    komisyon = komisyon_hesapla(quantity, price)
    return brut, komisyon, round(brut + komisyon, 2)


def satim_geliri(quantity: float, price: float) -> Tuple[float, float, float]:
    """
    (brüt_tutar, komisyon, bakiyeye_eklenecek_net)

    Satımda komisyon geliri AZALTIR.
    """
    brut = round(quantity * price, 2)
    komisyon = komisyon_hesapla(quantity, price)
    return brut, komisyon, round(brut - komisyon, 2)


def record_transaction(
    db: Session,
    *,
    user_id: int,
    stock_id: int,
    action_type: str,
    quantity: float,
    price: float,
    average_cost: Optional[float] = None,
    source: str = "MANUAL",
    commission: Optional[float] = None,
) -> models.Transaction:
    """
    Gerçekleşmiş bir alım/satımı işlem geçmişine ekler.

    ÖNEMLİ: Bu fonksiyon `db.add` yapar ama COMMIT ETMEZ. Çağıran taraf zaten
    açık bir atomik transaction içindedir (begin_write_transaction) ve kaydı
    kendi commit'iyle kalıcı hale getirir. Böylece alım-satım geri alınırsa
    (rollback) işlem kaydı da geri alınır — geçmişte "olmamış işlem" görünmez.

    `average_cost` yalnızca SAT işlemlerinde anlamlıdır ve SATIŞTAN ÖNCEKİ
    ortalama maliyet olmalıdır. Gerçekleşen kâr/zarar buradan hesaplanıp
    kalıcı olarak yazılır; sonradan hesaplanamaz çünkü ortalama maliyet
    her yeni alımda değişir ve pozisyon tamamen satıldığında satır silinir.
    """
    action_type = action_type.upper()
    total_amount = round(quantity * price, 2)
    if commission is None:
        commission = komisyon_hesapla(quantity, price)

    # GERÇEKLEŞEN K/Z KOMİSYONDAN SONRADIR.
    # Alım komisyonu zaten `average_cost` içine gömülüdür (bkz. alim_maliyeti);
    # burada bir de satım komisyonu birim fiyattan düşülür. İkisi hesaba
    # katılmazsa kullanıcı, aslında zarar ettiği bir işlemi kâr sanabilir.
    realized_pnl = None
    if action_type == "SAT" and average_cost is not None:
        net_birim_fiyat = price - (commission / quantity if quantity else 0.0)
        realized_pnl = round((net_birim_fiyat - average_cost) * quantity, 2)

    entry = models.Transaction(
        user_id=user_id,
        stock_id=stock_id,
        action_type=action_type,
        quantity=quantity,
        price=price,
        total_amount=total_amount,
        commission=commission,
        realized_pnl=realized_pnl,
        average_cost_at_trade=round(average_cost, 2) if average_cost is not None else None,
        source=source,
    )
    db.add(entry)
    return entry
