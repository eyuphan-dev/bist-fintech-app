"""
katilim.py
----------
Katılım (helal finans) uygunluk taraması — gerçek bilanço oranlarıyla.

NEDEN BU MODÜL VAR:
Uygulamada katılım uygunluğu bugüne kadar elle küratörlü bir bayraktı: bir
hisse ya "uygun" ya "uygun değil" görünüyordu, ama KULLANICI NEDENİNİ
GÖREMİYORDU ve veri elle güncellenmediği sürece bayatlıyordu. Katılım Endeksi
de üyelik listesini yayımlar, ölçütlerin ne kadarına yaklaşıldığını değil.
Burada aynı ölçütler şirketin kendi bilançosundan hesaplanır; böylece hem
gerekçe gösterilebilir hem de "eşiğe yaklaşıyor" uyarısı verilebilir.

UYGULANAN ÖLÇÜTLER
  1. Faaliyet alanı  — şirketin işi katılım ilkeleriyle bağdaşmalı.
  2. Finansal borç / piyasa değeri  < %33
  3. Nakit + finansal yatırımlar / piyasa değeri  < %33

UYGULANAMAYAN ÖLÇÜT (dürüstlük notu)
  Endeksin dördüncü ölçütü "uygun olmayan gelirlerin toplam gelire oranı
  < %5"tir. Bu kalem yalnızca KAP dipnotlarında ayrıştırılmış olarak bulunur,
  yfinance'ta hiç yoktur. Uydurmak yerine hesaplanmadığı açıkça bildirilir;
  bu yüzden sonuç "endeks üyeliği" değil, ÖN TARAMA olarak sunulur.

TERİMLER ÜZERİNE
  Ölçütler Katılım Endeksi'nin kendi yayımladığı terminolojiyle ("finansal
  borç", "nakit ve finansal yatırımlar") ifade edilir. Bu hem doğru terim hem
  de road_map.md'deki dil kuralıyla uyumludur.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

import models

# Endeks ölçütlerinin üst sınırı.
ESIK = 33.0
# Bu değerin üzerindeki bir oran henüz eşiği aşmamıştır ama tehlikeye yakındır.
UYARI_ESIGI = 28.0

# Faaliyet alanı gereği uygun sayılmayan sektörler. Katalogdaki Türkçe sektör
# sözlüğüyle birebir eşleşir (bkz. init_db.INITIAL_STOCKS).
UYGUNSUZ_SEKTORLER = {
    "Bankacılık": "Şirketin ana faaliyeti katılım ilkeleriyle bağdaşmayan bankacılıktır.",
    "Sigorta": "Geleneksel sigortacılık faaliyeti katılım ilkeleriyle bağdaşmaz.",
    "Aracı Kurum": "Ana faaliyet alanı katılım ilkeleri açısından uygun görülmez.",
    "Finansal Kiralama": "Finansal kiralama faaliyeti ayrıca değerlendirme gerektirir.",
}


def _f(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # NaN kontrolü


def _son_bilanco(db: Session, stock_id: int) -> Optional[models.FinancialStatement]:
    return (
        db.query(models.FinancialStatement)
        .filter_by(stock_id=stock_id)
        .order_by(models.FinancialStatement.period_end.desc())
        .first()
    )


def hisseyi_tara(db: Session, stock: models.Stock) -> dict:
    """
    Tek bir hisseyi tarar ve sonucu döner (veritabanına YAZMAZ).

    Dönen sözlük: status, debt_ratio, asset_ratio, detail, uyari
    """
    sonuc = {
        "status": "BELIRSIZ",
        "debt_ratio": None,
        "asset_ratio": None,
        "detail": None,
        "uyari": None,
    }

    # --- 1. Faaliyet alanı ---------------------------------------------------
    gerekce = UYGUNSUZ_SEKTORLER.get(stock.sector or "")
    if gerekce:
        sonuc["status"] = "UYGUN_DEGIL"
        sonuc["detail"] = gerekce
        return sonuc

    # --- Piyasa değeri -------------------------------------------------------
    analysis = db.query(models.CompanyAnalysis).filter_by(stock_id=stock.id).first()
    market_cap = _f(getattr(analysis, "market_cap", None)) if analysis else None
    if not market_cap or market_cap <= 0:
        sonuc["detail"] = "Piyasa değeri verisi olmadığı için oranlar hesaplanamadı."
        return sonuc

    bilanco = _son_bilanco(db, stock.id)
    if bilanco is None:
        sonuc["detail"] = "Şirketin bilanço verisi henüz alınmadı."
        return sonuc

    # --- 2. Finansal borç oranı ---------------------------------------------
    borc = _f(bilanco.total_debt)
    if borc is None:
        sonuc["detail"] = "Bilançoda finansal borç kalemi bulunamadı."
        return sonuc
    debt_ratio = round(borc / market_cap * 100, 2)
    sonuc["debt_ratio"] = debt_ratio

    # --- 3. Nakit ve finansal yatırımlar oranı -------------------------------
    nakit = _f(bilanco.cash_and_equivalents) or 0.0
    yatirim = _f(bilanco.short_term_investments) or 0.0
    # İki kalem de boşsa oran hesaplanmış sayılmaz; 0 yazmak "tertemiz" gibi
    # yanlış bir izlenim verirdi.
    if bilanco.cash_and_equivalents is None and bilanco.short_term_investments is None:
        asset_ratio = None
    else:
        asset_ratio = round((nakit + yatirim) / market_cap * 100, 2)
    sonuc["asset_ratio"] = asset_ratio

    # --- Karar ---------------------------------------------------------------
    ihlaller = []
    if debt_ratio >= ESIK:
        ihlaller.append(f"finansal borç oranı %{debt_ratio:.1f} (sınır %{ESIK:.0f})")
    if asset_ratio is not None and asset_ratio >= ESIK:
        ihlaller.append(f"nakit ve finansal yatırımlar oranı %{asset_ratio:.1f} (sınır %{ESIK:.0f})")

    if ihlaller:
        sonuc["status"] = "UYGUN_DEGIL"
        sonuc["detail"] = "Ön tarama sınırı aşıldı: " + ", ".join(ihlaller) + "."
        return sonuc

    # Nakit oranı hesaplanamadıysa sonucu "uygun" ilan etmek fazla iddialı olur.
    if asset_ratio is None:
        sonuc["detail"] = (
            f"Finansal borç oranı %{debt_ratio:.1f} ile sınırın altında, ancak nakit ve "
            "finansal yatırımlar kalemi bilançoda bulunamadığı için tarama tamamlanamadı."
        )
        return sonuc

    sonuc["status"] = "UYGUN"
    sonuc["detail"] = (
        f"Ön taramayı geçti — finansal borç oranı %{debt_ratio:.1f}, nakit ve finansal "
        f"yatırımlar oranı %{asset_ratio:.1f} (her ikisinin sınırı %{ESIK:.0f})."
    )

    # Eşiğe yaklaşma uyarısı: kimse bunu önceden söylemiyor.
    yakin = [
        (ad, oran)
        for ad, oran in (("finansal borç", debt_ratio), ("nakit ve finansal yatırımlar", asset_ratio))
        if oran >= UYARI_ESIGI
    ]
    if yakin:
        sonuc["uyari"] = (
            "Sınıra yaklaşıyor: "
            + ", ".join(f"{ad} oranı %{oran:.1f}" for ad, oran in yakin)
            + f" (sınır %{ESIK:.0f}). Gelecek bilançoda uygunluk değişebilir."
        )

    return sonuc


def tum_katalogu_tara(db: Session) -> dict:
    """
    Aktif tüm hisseleri tarar ve sonucu veritabanına yazar.

    ELLE KÜRATÖRLÜ VERİ EZİLMEZ: is_katilim_compliant değeri elle girilmiş
    hisselerde (arınma oranı da yayımlanmış olanlar) o kayıt daha güvenilirdir
    çünkü endeksin kendi listesine dayanır. Hesaplanan oranlar yine de yazılır
    ki kullanıcı gerekçeyi ve eşiğe yaklaşmayı görebilsin.
    """
    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    sayac = {"UYGUN": 0, "UYGUN_DEGIL": 0, "BELIRSIZ": 0}
    simdi = datetime.utcnow()

    for stock in stocks:
        try:
            sonuc = hisseyi_tara(db, stock)
        except Exception as e:
            print(f"[Katılım] {stock.symbol}: tarama hatası ({e})")
            continue

        stock.katilim_debt_ratio = sonuc["debt_ratio"]
        stock.katilim_asset_ratio = sonuc["asset_ratio"]
        stock.katilim_checked_at = simdi
        detay = sonuc["detail"]
        if sonuc["uyari"]:
            detay = f"{detay} {sonuc['uyari']}"
        stock.katilim_detail = detay

        # Küratörlü kayıt varsa durum ondan gelir; yoksa hesaplanan kullanılır.
        kuratorlu = _f(stock.purification_rate) not in (None, 0.0) or bool(stock.non_compliance_reason)
        if not kuratorlu:
            stock.katilim_status = sonuc["status"]
            stock.is_katilim_compliant = sonuc["status"] == "UYGUN"

        sayac[stock.katilim_status or "BELIRSIZ"] = sayac.get(stock.katilim_status or "BELIRSIZ", 0) + 1

    db.commit()
    print(f"[Katılım] Tarama tamamlandı: {sayac}")
    return sayac
