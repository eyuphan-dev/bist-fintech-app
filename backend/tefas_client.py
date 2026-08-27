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
from text_utils import tr_fold

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

# Fon adından katılım (faizsiz) uygunluğunu yakalayan anahtar kelimeler.
# Eşleştirme text_utils.tr_fold ile yapılır: TEFAS fon adlarını TAMAMI BÜYÜK
# HARF döndürür ("... KISA VADELİ KATILIM SERBEST FONU") ve "KATILIM".lower()
# ASCII "katilim" üretirken insanın yazdığı anahtar kelime "katılım"dır —
# ikisi eşleşmez. Bu liste eskiden hiç kullanılmıyordu ve kullanılsaydı da
# tr_fold olmadan sıfır eşleşme verirdi (ölçüldü).
# "kira sertifika" KÖK olarak yazılır: TEFAS hem "KİRA SERTİFİKASI" hem
# "KİRA SERTİFİKALARI" kullanıyor ve tam biçim yazılırsa çoğul olan eşleşmez.
KATILIM_KEYWORDS = ("katilim", "kira sertifika", "faizsiz")

# Fon adından TEFAS tür etiketini tahmin eder; TEFAS anlık görüntüsü tür
# bilgisini ayrı bir alanda vermiyor.
_TUR_ISARETLERI = (
    ("kira sertifika", "Kira Sertifikası"),
    ("hisse senedi", "Hisse Senedi"),
    ("degisken", "Değişken"),
    ("serbest", "Serbest"),
    ("para piyasasi", "Para Piyasası"),
    ("endeks", "Endeks"),
    ("altin", "Altın"),
    ("emeklilik", "Emeklilik"),
    ("katilim", "Katılım"),
)


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


def update_tefas_funds(db: Session, fund_codes: Optional[List[str]] = None,
                       snapshot: Optional[List[Dict[str, Any]]] = None) -> int:
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

    if snapshot is None:
        snapshot = _fetch_all_snapshots()

    # fund_code -> [{"price":..., "date": "YYYY-MM-DD"}, ...] (tarihe göre sıralı)
    history_by_code: Dict[str, List[Dict[str, Any]]] = {}
    for row in snapshot:
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


def _tur_tahmin(ad: str) -> Optional[str]:
    """Fon adından TEFAS tür etiketini çıkarır; tanınmazsa None."""
    katlanmis = tr_fold(ad)
    for isaret, etiket in _TUR_ISARETLERI:
        if isaret in katlanmis:
            return etiket
    return None


def _katilim_mi(ad: str) -> bool:
    """Fon adı katılım (faizsiz) fonuna işaret ediyor mu."""
    katlanmis = tr_fold(ad)
    return any(kw in katlanmis for kw in KATILIM_KEYWORDS)


def discover_katilim_funds(db: Session, limit: int = 500,
                           snapshot: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    TEFAS anlık görüntüsündeki TÜM fonları tarar ve adı katılım (faizsiz)
    fonuna işaret edenleri `funds` tablosuna ekler. Eklenen yeni fon sayısını
    döner.

    NEDEN: `update_tefas_funds` zaten her fon tipi için TÜM fonları (ölçüldü:
    2.470 benzersiz fon) tek istekte indiriyordu, sonra elle yazılmış 3 fonluk
    `seed_katilim_funds` listesinde olmayan her şeyi çöpe atıyordu. Yani veri
    zaten elimizdeydi, sadece kullanılmıyordu. Keşif ek bir ağ isteği
    getirmez — aynı yanıtı okur.

    Fon adına bakmak mükemmel bir ölçüt değil (TEFAS bu uçta katılım bayrağı
    vermiyor), ama "KATILIM" / "KİRA SERTİFİKASI" ibaresi fon unvanında SPK
    tarafından zorunlu tutulur; bu yüzden ad temelli eşleşme uydurma bir skor
    değil, resmi unvana dayanan doğrulanabilir bir ölçüttür.
    """
    if snapshot is None:
        snapshot = _fetch_all_snapshots()

    adaylar: Dict[str, str] = {}  # kod -> ad
    for row in snapshot:
        kod = (row.get("fonKodu") or "").strip().upper()
        ad = (row.get("fonUnvan") or "").strip()
        if not kod or not ad or kod in adaylar:
            continue
        if _katilim_mi(ad):
            adaylar[kod] = ad

    mevcut = {f.code.upper() for f in db.query(models.Fund).all()}
    eklenen = 0
    for kod, ad in sorted(adaylar.items()):
        if kod in mevcut:
            continue
        if len(mevcut) + eklenen >= limit:
            # Sınır ALFABETİK sırada keser; bu yüzden sınır aday sayısının
            # (ölçüldü: 388) rahatça üstünde tutulmalı, yoksa sondaki harfle
            # başlayan fonlar sessizce düşer.
            print(f"[TefasClient] UYARI: {limit} fon sınırına ulaşıldı, kalan adaylar atlandı.")
            break
        db.add(models.Fund(
            code=kod,
            name=ad[:200],
            fund_type=_tur_tahmin(ad),
            risk_level=None,  # TEFAS bu uçta risk seviyesi vermiyor; uydurmuyoruz.
            is_katilim_compliant=True,
        ))
        eklenen += 1

    db.commit()
    print(f"[TefasClient] Katılım fonu taraması: {len(adaylar)} aday, {eklenen} yeni fon eklendi.")
    return eklenen


def _fetch_all_snapshots() -> List[Dict[str, Any]]:
    """
    Üç fon tipinin anlık görüntüsünü TEK SEFER çekip birleştirir.

    NEDEN PAYLAŞILIYOR: `discover_katilim_funds` ve `update_tefas_funds` aynı
    veriyi istiyor. Her biri kendi isteğini atarsa 3 + 3 = 6 istek olur ve bu
    TEFAS'ın ~6 istek/dakika sınırının tam sınırındadır — ölçüldü: ikisi arka
    arkaya çağrıldığında ikincisi 429 Too Many Requests aldı ve fon fiyatları
    hiç güncellenmedi. Tek çekim bunu 3 isteğe indirir.
    """
    today = datetime.now()
    from_date = today - timedelta(days=6)
    birlesik: List[Dict[str, Any]] = []
    for kind in FUND_KINDS:
        try:
            birlesik.extend(_fetch_kind_snapshot(kind, from_date, today))
        except Exception as e:
            print(f"[TefasClient] {kind} tipi çekilemedi: {e}")
    return birlesik


def sync_tefas(db: Session) -> Dict[str, int]:
    """
    TEFAS senkronizasyonunun tek giriş noktası: anlık görüntüyü BİR KEZ çeker,
    önce yeni katılım fonlarını keşfeder, sonra tüm takip edilen fonların
    fiyatını günceller. Scheduler bunu çağırmalıdır.
    """
    snapshot = _fetch_all_snapshots()
    if not snapshot:
        print("[TefasClient] TEFAS anlık görüntüsü boş, senkronizasyon atlandı.")
        return {"kesfedilen": 0, "guncellenen": 0}
    kesfedilen = discover_katilim_funds(db, snapshot=snapshot)
    guncellenen = update_tefas_funds(db, snapshot=snapshot)
    return {"kesfedilen": kesfedilen, "guncellenen": guncellenen}
