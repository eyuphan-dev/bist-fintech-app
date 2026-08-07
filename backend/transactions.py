"""
Kullanıcı işlem geçmişi kaydı (Transaction) için ortak yardımcı.

Neden ayrı modül: kayıt hem anlık işlemlerde (main.py -> /api/trade) hem de
bekleyen emirlerin gerçekleşmesinde (orders.py -> _execute_single_order)
yazılıyor. Aynı mantığı iki yere kopyalarsak zamanla ayrışır (örneğin
gerçekleşen K/Z formülü bir tarafta güncellenip diğerinde unutulur).
main.py <-> orders.py arasında dairesel import riski olmasın diye bu modül
ikisinden de bağımsız durur; yalnızca models'a bağlıdır.
"""

from typing import Optional

from sqlalchemy.orm import Session

import models


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

    realized_pnl = None
    if action_type == "SAT" and average_cost is not None:
        realized_pnl = round((price - average_cost) * quantity, 2)

    entry = models.Transaction(
        user_id=user_id,
        stock_id=stock_id,
        action_type=action_type,
        quantity=quantity,
        price=price,
        total_amount=total_amount,
        realized_pnl=realized_pnl,
        average_cost_at_trade=round(average_cost, 2) if average_cost is not None else None,
        source=source,
    )
    db.add(entry)
    return entry
