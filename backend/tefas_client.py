"""
tefas_client.py
----------------
TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) günlük fon fiyatlarını
çeken istemci. TEFAS'ın resmi dokümante edilmiş bir API'si yoktur; bu modül
tefas.gov.tr'nin kendi web arayüzünün kullandığı genel BindHistoryInfo
uç noktasını (yaygın olarak açık kaynak TEFAS scraper'larında kullanılır) baz alır.
Uç değişirse fonksiyonlar sessizce boş sonuç döner, uygulamayı düşürmez.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests
from sqlalchemy.orm import Session

import models

TEFAS_HISTORY_URL = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
TEFAS_COMPARE_URL = "https://www.tefas.gov.tr/api/DB/BindComparisonFundReturns"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
    "Origin": "https://www.tefas.gov.tr",
}

# Katılım (Faizsiz) endeksine giren yaygın fon tipi anahtar kelimeleri
KATILIM_KEYWORDS = ["katılım", "katilim", "kira sertifikası", "kira sertifikasi"]


def fetch_fund_history(fund_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """
    TEFAS'tan tek bir fon için tarihsel fiyat geçmişini çeker.
    Tarihler 'DD.MM.YYYY' formatında olmalıdır.
    """
    payload = {
        "fontip": "YAT",
        "bastarih": start_date,
        "bittarih": end_date,
        "fonkod": fund_code,
    }
    try:
        resp = requests.post(TEFAS_HISTORY_URL, data=payload, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        rows = data.get("data", [])
        parsed = []
        for row in rows:
            parsed.append({
                "price": float(row.get("FIYAT", 0) or 0),
                "date": row.get("TARIH", ""),
            })
        return parsed
    except Exception as e:
        print(f"[TefasClient] Fon geçmişi çekme hatası ({fund_code}): {e}")
        return []


def update_tefas_funds(db: Session, fund_codes: Optional[List[str]] = None) -> int:
    """
    Takip edilen fonlar için TEFAS'tan son fiyatı çeker, funds/fund_prices
    tablolarını günceller. fund_codes verilmezse veritabanındaki tüm fonlar kullanılır.
    Döner: güncellenen fon sayısı.
    """
    funds = db.query(models.Fund).all()
    if fund_codes:
        funds = [f for f in funds if f.code in fund_codes]

    if not funds:
        print("[TefasClient] Takip edilen fon bulunamadı (funds tablosu boş).")
        return 0

    today = datetime.now()
    start = (today - timedelta(days=7)).strftime("%d.%m.%Y")
    end = today.strftime("%d.%m.%Y")

    updated = 0
    for fund in funds:
        history = fetch_fund_history(fund.code, start, end)
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
    # TEFAS "TARIH" alanı genelde "/Date(1700000000000)/" epoch-ms formatındadır
    try:
        if date_str.startswith("/Date("):
            epoch_ms = int(date_str.replace("/Date(", "").replace(")/", "").split("+")[0])
            return datetime.utcfromtimestamp(epoch_ms / 1000).date()
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except Exception:
        return None
