"""
push.py
-------
Web Push (tarayıcı bildirimi) gönderimi.

NEDEN GEREKLİ:
Alarm motoru (notifications.py) zaten çalışıyordu ama teslimat yalnızca
uygulama içi zildi — kullanıcı uygulamayı açmazsa alarmdan haberi olmuyordu,
ki alarmın bütün amacı buydu. Bu modül aynı bildirimleri işletim sistemi
bildirimi olarak da gönderir.

TASARIM NOTLARI:
- Gönderim ASLA çağıranı patlatmaz. Bildirim kaydı veritabanına yazılmıştır;
  push gönderilemezse kullanıcı bildirimi uygulama içinde yine görür. Bu yüzden
  tüm hatalar yutulur ve loglanır.
- Push gönderimi HTTP çağrısıdır ve yavaş olabilir. Bu yüzden veritabanı
  COMMIT'inden SONRA çağrılır: commit'i bekleten bir ağ çağrısı, tetikleyici
  işini gereksiz yere uzatır ve hata durumunda bildirimin hiç kaydedilmemesine
  yol açabilirdi.
- 404/410 dönen abonelikler KALICI OLARAK ÖLÜDÜR (kullanıcı uygulamayı
  kaldırmış veya bildirimleri kapatmıştır); bunlar hemen silinir, yoksa her
  turda boşuna denenip yavaşlatırlar.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

import models

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "").strip()
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").strip()
# RFC 8292: push servisleri, sorun çıktığında ulaşabilecekleri bir iletişim
# adresi ister. Boş bırakılırsa bazı servisler (özellikle Apple) reddeder.
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:destek@borsa-trader.duckdns.org").strip()

# Push yükü şifrelenmiş olarak gönderilir ve servislerin çoğu 4 KB sınırı koyar.
# Uzun KAP başlıkları bu sınırı zorlayabildiği için metinler kırpılır.
MAX_TITLE = 80
MAX_BODY = 180


def is_configured() -> bool:
    """VAPID anahtarları tanımlı mı? Değilse push sessizce devre dışıdır."""
    return bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_payload(
    title: str,
    body: str,
    *,
    url: str = "/",
    tag: Optional[str] = None,
) -> dict[str, Any]:
    """Service worker'ın `push` olayında beklediği yapı."""
    return {
        "title": _truncate(title, MAX_TITLE),
        "body": _truncate(body, MAX_BODY),
        "url": url,
        # Aynı tag'li bildirimler cihazda birbirinin üstüne yazılır; örneğin bir
        # hisse için arka arkaya gelen alarmlar bildirim merkezini doldurmaz.
        "tag": tag or "bist",
    }


def send_to_user(db: Session, user_id: int, payload: dict[str, Any]) -> int:
    """
    Kullanıcının TÜM cihazlarına gönderir. Ulaşan cihaz sayısını döner.

    Hiçbir koşulda istisna fırlatmaz.
    """
    if not is_configured():
        return 0

    subs = db.query(models.PushSubscription).filter_by(user_id=user_id).all()
    if not subs:
        return 0

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        print("[Push] pywebpush kurulu değil, gönderim atlandı.")
        return 0

    data = json.dumps(payload, ensure_ascii=False)
    delivered = 0
    dead: list[models.PushSubscription] = []

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=data,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
                # TTL varsayilani 0'dir: cihaz o an ulasilamazsa bildirim
                # SESSIZCE ATILIR. Metroda/tunelde olan kullanici alarmini hic
                # gormezdi. 1 saat, kisa kopukluklari kurtaracak kadar uzun,
                # bayat bir fiyat alarmi gondermeyecek kadar kisa.
                ttl=3600,
                timeout=10,
            )
            sub.last_success_at = datetime.utcnow()
            sub.failure_count = 0
            delivered += 1
        except WebPushException as e:
            status = getattr(e.response, "status_code", None)
            if status in (404, 410):
                # Abonelik kalıcı olarak geçersiz — kullanıcı uygulamayı
                # kaldırmış veya bildirim iznini geri almış.
                dead.append(sub)
            else:
                sub.failure_count = (sub.failure_count or 0) + 1
                print(f"[Push] gönderilemedi (user={user_id}, http={status}): {e}")
        except Exception as e:
            sub.failure_count = (sub.failure_count or 0) + 1
            print(f"[Push] beklenmeyen hata (user={user_id}): {e}")

    for sub in dead:
        db.delete(sub)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Push] abonelik durumu kaydedilemedi: {e}")

    return delivered


def send_outbox(db: Session, outbox: list[dict[str, Any]]) -> int:
    """
    notifications.py'nin biriktirdiği kutuyu gönderir.

    Kutu, veritabanı COMMIT'inden sonra boşaltılır: aksi halde geri alınan
    (rollback) bir işlem için bildirim gönderilmiş olabilirdi.
    """
    if not outbox or not is_configured():
        return 0
    total = 0
    for item in outbox:
        total += send_to_user(db, item["user_id"], item["payload"])
    return total
