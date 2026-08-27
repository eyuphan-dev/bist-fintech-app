"""
kap_search.py
--------------
KAP bildirimlerinde tam metin arama.

498 bildirimin (`kap_notifications`) başlık + özetinde arama yapılır.
"AI özet" gibi ileride gelebilecek özelliklerin doğal ön adımı: önce metni
bulabilmek, sonra özetlemek.

İKİ AYRI YOL, TEK VERİTABANI FARKI İÇİN: üretimde PostgreSQL, yerelde SQLite
kullanılıyor (bkz. database.py, projem.md §9). PostgreSQL'in yerleşik Türkçe
metin arama yapılandırması (`to_tsvector('turkish', ...)`) kullanılır — sunucuda
mevcut olduğu doğrulandı. SQLite'ta bu yapılandırma yoktur; yerel geliştirmede
basit alt dize eşleşmesine düşülür. `tr_lower` kullanılır ki büyük "İ" ile
başlayan başlıklarda (KAP metinlerinde yaygın) arama sessizce başarısız olmasın
— aynı hata `insider_client.py`de ölçülerek bulunmuştu.

DİKKAT — database.IS_SQLITE KULLANILMAZ: o bayrak "DATABASE_URL hiç
tanımlanmadı mı" sorusuna cevap verir, gerçek motor diyalektine değil. Biri
`DATABASE_URL=sqlite:///...` ile AÇIKÇA sqlite verirse IS_SQLITE False kalır
ve to_tsvector sorgusu SQLite'ta "unrecognized token: @" hatasıyla patlar
(ölçülerek bulundu — bu projedeki test betiklerinin neredeyse tamamı böyle
başlatılıyor). Bunun yerine `engine.dialect.name` ile GERÇEK diyalekt
sorgulanır.

ÖLÇEK NOTU: 498 satırlık bir tabloda GIN indeksi olmadan `to_tsvector` her
sorguda anında hesaplanır, bu ölçekte sorun yaratmaz. Bildirim sayısı on
binlere çıkarsa (örn. tüm KAP arşivi çekilirse) kalıcı bir `tsvector` kolonu +
GIN indeksi eklenmeli — bkz. projem.md "ROW_NUMBER() bölümün tamamını okur"
uyarısıyla aynı sınıf tuzak: indekssiz sorgu veri büyüdükçe doğrusal yavaşlar.
"""

from typing import List

from sqlalchemy import func, text
from sqlalchemy.orm import Session

import models
from database import engine
from text_utils import tr_lower

MAX_RESULTS = 30
# SQLite yolunda tarama yapılacak üst sınır — tüm tabloyu belleğe çekmemek için.
SQLITE_SCAN_LIMIT = 3000


def search_kap_notifications(db: Session, query: str, limit: int = MAX_RESULTS) -> List[models.KapNotification]:
    query = (query or "").strip()
    if not query:
        return []
    limit = max(1, min(limit, MAX_RESULTS))

    if engine.dialect.name == "sqlite":
        return _search_sqlite(db, query, limit)
    return _search_postgres(db, query, limit)


def _search_postgres(db: Session, query: str, limit: int) -> List[models.KapNotification]:
    vector = func.to_tsvector(
        "turkish",
        func.coalesce(models.KapNotification.title, "") + " " + func.coalesce(models.KapNotification.summary, ""),
    )
    tsquery = func.plainto_tsquery("turkish", query)
    return (
        db.query(models.KapNotification)
        .filter(vector.op("@@")(tsquery))
        .order_by(func.ts_rank(vector, tsquery).desc(), models.KapNotification.publish_date.desc())
        .limit(limit)
        .all()
    )


def _search_sqlite(db: Session, query: str, limit: int) -> List[models.KapNotification]:
    # Türkçe metin arama yapılandırması SQLite'ta yok; alt dize eşleşmesine
    # düşülür. Yalnızca yerel geliştirmede çalışır, üretim yolu değildir.
    q_lower = tr_lower(query)
    rows = (
        db.query(models.KapNotification)
        .order_by(models.KapNotification.publish_date.desc())
        .limit(SQLITE_SCAN_LIMIT)
        .all()
    )
    sonuc = [
        r for r in rows
        if q_lower in tr_lower(r.title or "") or q_lower in tr_lower(r.summary or "")
    ]
    return sonuc[:limit]
