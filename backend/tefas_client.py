"""
tefas_client.py
----------------
TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) günlük fon fiyatlarını
çeken istemci.

NOT (2026-08-03): TEFAS 2026'da eski "fundturkey.com.tr/api/DB/BindHistoryInfo"
uç noktasını tamamen kaldırdı (artık 404 "Method not found or disabled"
dönüyor) — bu yüzden fon fiyatları hiçbir zaman güncellenmiyordu. Yeni resmi
API "www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir" kullanılarak canlı test
edildi (gerçek fiyat/tarih verisi doğrulandı). TEFAS bu uç noktada dakikada
~6 istek sınırı uyguluyor; bu yüzden fon başına ayrı istek atmak yerine, her
fon TİPİ (YAT/EMK/BYF) için TEK istekte TÜM fonların anlık görüntüsü çekilip
takip edilen fon kodlarına göre istemci tarafında eşleştirilir.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests
from sqlalchemy.orm import Session

import models

TEFAS_INFO_URL = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
}

# funds tablosundaki fon_type alanları bu tiplerin dışına genelde çıkmıyor;
# üçünü de taramak fon başına tek tek istek atmaktan çok daha ucuz.
FUND_KINDS = ("YAT", "EMK", "BYF")

# TEFAS'ın "veri yok" (tatil/hafta sonu vb.) durumunda döndürdüğü zararsız hata
# metinleri — bunlar gerçek bir hata değil, boş sonuç olarak yorumlanır.
EMPTY_RESULT_MARKERS = ("out of bounds", "veri bulunamadı", "null\" because")

# Katılım (Faizsiz) endeksine giren yaygın fon tipi anahtar kelimeleri
KATILIM_KEYWORDS = ["katılım", "katilim", "kira sertifikası", "kira sertifikasi"]


def _fetch_kind_snapshot(kind: str, from_date: datetime, to_date: datetime) -> List[Dict[str, Any]]:
    """
    Belirli bir fon tipi için tarih aralığındaki TÜM fonların (fiyat, tarih,
    fon adı vb.) anlık görüntüsünü tek istekte çeker.
    """
    body = {
        "fonTipi": kind,
        "fonKodu": None,
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "kurucuKod": None,
        "basTarih": from_date.strftime("%Y%m%d"),
        "bitTarih": to_date.strftime("%Y%m%d"),
        "basSira": 1,
        "bitSira": 100000,
        "dil": "TR",
        "sFonTurKod": "",
        "fonKod": "",
        "fonGrup": "",
        "fonUnvanTip": "",
    }
    resp = requests.post(TEFAS_INFO_URL, json=body, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    err_msg = (data.get("errorMessage") or "").lower()
    if err_msg and not any(marker in err_msg for marker in EMPTY_RESULT_MARKERS):
        raise RuntimeError(f"TEFAS API hatası ({kind}): {data.get('errorMessage')}")

    return data.get("resultList") or []


def update_tefas_funds(db: Session, fund_codes: Optional[List[str]] = None) -> int:
    """
    Takip edilen fonlar için TEFAS'tan son fiyatı çeker, fund_prices tablosunu
    günceller. fund_codes verilmezse veritabanındaki tüm fonlar kullanılır.
    Döner: güncellenen fon sayısı.
    """
    funds = db.query(models.Fund).all()
    if fund_codes:
        funds = [f for f in funds if f.code in fund_codes]

    if not funds:
        print("[TefasClient] Takip edilen fon bulunamadı (funds tablosu boş).")
        return 0

    tracked_codes = {f.code.upper() for f in funds}
    today = datetime.now()
    # Son 2 iş günü (hafta sonu/tatil güvenliği için 4 gün geriye bakılır),
    # daily_return hesaplamak için en az 2 fiyat noktası gerekiyor.
    from_date = today - timedelta(days=4)

    # fund_code -> [{"price":..., "date": "YYYY-MM-DD"}, ...] (tarihe göre sıralı)
    history_by_code: Dict[str, List[Dict[str, Any]]] = {}
    for kind in FUND_KINDS:
        try:
            rows = _fetch_kind_snapshot(kind, from_date, today)
        except Exception as e:
            print(f"[TefasClient] {kind} tipi fon verisi çekilemedi: {e}")
            continue
        for row in rows:
            code = (row.get("fonKodu") or "").upper()
            if code not in tracked_codes:
                continue
            price = row.get("fiyat")
            date_str = row.get("tarih")
            if price is None or not date_str:
                continue
            history_by_code.setdefault(code, []).append({
                "price": float(price),
                "date": date_str,
            })

    updated = 0
    for fund in funds:
        history = history_by_code.get(fund.code.upper())
        if not history:
            continue

        history.sort(key=lambda r: r["date"])
        latest = history[-1]
        prev = history[-2] if len(history) > 1 else None

        daily_return = None
        if prev and prev["price"] > 0:
            daily_return = round(((latest["price"] - prev["price"]) / prev["price"]) * 100, 2)

        recorded_date = _parse_tefas_date(latest["date"]) or today.date()

        existing = (
            db.query(models.FundPrice)
            .filter_by(fund_id=fund.id, recorded_date=recorded_date)
            .first()
        )
        if existing:
            existing.price = latest["price"]
            existing.daily_return = daily_return
        else:
            db.add(models.FundPrice(
                fund_id=fund.id,
                price=latest["price"],
                daily_return=daily_return,
                monthly_return=None,
                yearly_return=None,
                recorded_date=recorded_date,
            ))
        updated += 1

    db.commit()
    print(f"[TefasClient] {updated} fon fiyatı güncellendi.")
    return updated


def seed_katilim_funds(db: Session) -> None:
    """Yaygın bilinen Katılım (faizsiz) endeksi fonlarını funds tablosuna ekler (varsa dokunmaz)."""
    seed_list = [
        {"code": "AFT", "name": "Ak Portföy Katılım Endeksi Hisse Senedi Fonu", "fund_type": "Hisse Senedi", "risk_level": 6},
        {"code": "IPJ", "name": "İş Portföy Katılım Endeksi Hisse Senedi Fonu", "fund_type": "Hisse Senedi", "risk_level": 6},
        {"code": "KUT", "name": "Kuveyt Türk Katılım Kira Sertifikaları Fonu", "fund_type": "Kira Sertifikası", "risk_level": 2},
    ]
    for item in seed_list:
        exists = db.query(models.Fund).filter_by(code=item["code"]).first()
        if not exists:
            db.add(models.Fund(
                code=item["code"],
                name=item["name"],
                fund_type=item["fund_type"],
                risk_level=item["risk_level"],
                is_katilim_compliant=True,
            ))
    db.commit()


def _parse_tefas_date(date_str: str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None
