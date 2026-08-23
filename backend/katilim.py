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
  2. Finansal borç / toplam varlık  < %33
  3. Nakit + finansal yatırımlar / toplam varlık  < %33

PAYDA NEDEN TOPLAM VARLIK (ölçülerek bulundu):
  İlk uygulamada payda piyasa değeriydi ve sonuçlar saçmaydı: SISE %143,
  PETKM %99.7, EREGL %60.7 çıkıyordu — oysa üçü de endeks üyesi. Aynı
  şirketler toplam varlık paydasıyla sırasıyla %31.7, %31.6 ve %27.0 veriyor,
  yani sınırın hemen altına oturuyorlar. Bu tesadüf değil: BIST Katılım
  Endeksi paydada toplam varlığı kullanır (piyasa değerini kullanan, Dow Jones
  Islamic gibi yurt dışı endeksleridir). Ek fayda: artık piyasa değeri verisi
  gerekmediği için yalnızca bilançosu olan her hisse taranabiliyor.

TARAMA KARAR VERMEZ — ÖLÇÜLDÜ, YETMİYOR
  Sonuçlar elle küratörlü 43 hisseyle karşılaştırıldı: hesaplanabilen 36
  hissenin 25'inde uyum, 11'inde ayrışma çıktı (%69). Ayrışmaların sebepleri
  tek tek belirlendi ve HİÇBİRİ elimizdeki veriyle kapatılamıyor:
    • ALBRK bir katılım bankasıdır ama sektör taraması yalnızca "Bankacılık"
      etiketini görür; katılım bankasını geleneksel bankadan ayıramaz.
    • KCHOL, SAHOL gibi holdingler banka iştirakleri yüzünden uygun sayılmaz;
      sektör etiketi iştirak yapısını göstermez.
    • MGROS ürün karması (alkol) nedeniyle elenir; ürün kırılımı verisi yok.
    • GUNDG, ENKAI nakit oranında ayrışır: ölçüt yalnızca GETİRİLİ nakit ve
      menkul kıymetleri sayar, bilançodaki toplam nakit bunu ayırmaz.
  Bu yüzden tarama katilim_status'u ASLA DEĞİŞTİRMEZ. %69 isabetle 122 hisseye
  damga vurmak, damgasız bırakmaktan daha kötüdür. Tarama yalnızca oranları ve
  sınıra uzaklığı gösterir — zaten kimsenin göstermediği kısım budur.

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
        "debt_source": None,
    }

    # --- 1. Faaliyet alanı ---------------------------------------------------
    gerekce = UYGUNSUZ_SEKTORLER.get(stock.sector or "")
    if gerekce:
        sonuc["status"] = "UYGUN_DEGIL"
        sonuc["detail"] = gerekce
        return sonuc

    # --- Payda: toplam varlık ------------------------------------------------
    bilanco = _son_bilanco(db, stock.id)
    if bilanco is None:
        sonuc["detail"] = "Şirketin bilanço verisi henüz alınmadı."
        return sonuc

    toplam_varlik = _f(bilanco.total_assets)
    if not toplam_varlik or toplam_varlik <= 0:
        sonuc["detail"] = "Bilançoda toplam varlık kalemi bulunamadığı için oranlar hesaplanamadı."
        return sonuc

    # --- 2. Finansal borç oranı ---------------------------------------------
    # Uzun + kısa vadeli finansal borç TERCİH EDİLİR; "Total Debt" ancak bunlar
    # yoksa kullanılır. Sebep ölçülerek bulundu: yfinance'in Total Debt kalemi
    # finansal kiralama yükümlülüklerini de içeriyor ve THYAO'da oranı %6.8
    # yerine %37.7 gösteriyordu (uçak kiralamaları). Katılım ölçütü kiralamayı
    # değil finansal borcu esas alır.
    uzun, kisa = _f(bilanco.long_term_debt), _f(bilanco.current_debt)
    if uzun is not None or kisa is not None:
        borc = (uzun or 0.0) + (kisa or 0.0)
        borc_kaynagi = "ayrisik"
    else:
        borc = _f(bilanco.total_debt)
        borc_kaynagi = "toplam"
    if borc is None:
        sonuc["detail"] = "Bilançoda finansal borç kalemi bulunamadı."
        return sonuc
    debt_ratio = round(borc / toplam_varlik * 100, 2)
    sonuc["debt_ratio"] = debt_ratio
    sonuc["debt_source"] = borc_kaynagi

    # --- 3. Nakit ve finansal yatırımlar oranı -------------------------------
    nakit = _f(bilanco.cash_and_equivalents) or 0.0
    yatirim = _f(bilanco.short_term_investments) or 0.0
    # İki kalem de boşsa oran hesaplanmış sayılmaz; 0 yazmak "tertemiz" gibi
    # yanlış bir izlenim verirdi.
    if bilanco.cash_and_equivalents is None and bilanco.short_term_investments is None:
        asset_ratio = None
    else:
        asset_ratio = round((nakit + yatirim) / toplam_varlik * 100, 2)
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


def _panel_metni(stock: "models.Stock", sonuc: dict) -> str:
    """
    Panelde gösterilecek metni üretir — KARAR CÜMLESİ KURMADAN.

    Rozetteki karar küratörlü endeks kaydından gelir, buradaki oranlar ise
    hesaptan. İkisi ayrışabildiği için bu metin asla "uygundur/uygun değildir"
    demez; oranları bildirir ve ayrışma varsa nedenini açıklar. Aksi halde
    rozet "UYGUN" derken panelin "sınır aşıldı" demesi gibi, arayüzün kendi
    kendini yalanladığı bir durum doğardı.
    """
    d, a = sonuc["debt_ratio"], sonuc["asset_ratio"]

    if d is None:
        # Oran yoksa yalnızca nedenini söyle. Sektör taramasının reddini
        # burada YAZMIYORUZ: ALBRK bir katılım bankasıdır ama sektör etiketi
        # "Bankacılık"tır; o metin uygun bir hissede yanlış görünürdü.
        neden = sonuc["detail"] or "Oranlar hesaplanamadı."
        if neden in UYGUNSUZ_SEKTORLER.values():
            return "Bu şirket için bilanço oranları hesaplanmadı; uygunluk faaliyet alanına göre değerlendirilir."
        return neden

    parcalar = [f"finansal borç / toplam varlık %{d:.1f}"]
    if a is not None:
        parcalar.append(f"nakit ve finansal yatırımlar / toplam varlık %{a:.1f}")
    metin = "Hesaplanan oranlar: " + ", ".join(parcalar) + f" (ön tarama sınırı %{ESIK:.0f})."

    asan = [ad for ad, oran in (("finansal borç", d), ("nakit ve finansal yatırımlar", a))
            if oran is not None and oran >= ESIK]
    mevcut = stock.katilim_status or ("UYGUN" if stock.is_katilim_compliant else None)

    if asan and mevcut == "UYGUN":
        metin += (
            f" {', '.join(asan).capitalize()} oranı ön tarama sınırının üzerinde olmasına rağmen"
            " hisse uygun kabul ediliyor. Bu ön tarama şirketin bilanço toplamlarını kullanır;"
            " endeks kendi tanımlarıyla (örneğin nakdin yalnızca getirili kısmı) hesaplar."
            " Bağlayıcı olan endeksin kararıdır."
        )
    elif asan:
        metin += f" {', '.join(asan).capitalize()} oranı sınırın üzerinde."
    elif sonuc["uyari"]:
        metin += " " + sonuc["uyari"]
    return metin


def tum_katalogu_tara(db: Session) -> dict:
    """
    Aktif tüm hisseleri tarar; ORANLARI yazar, KARARI değiştirmez.

    Neden karar değiştirmiyor: bkz. modül başlığındaki doğruluk ölçümü.
    Hesap küratörlü veriyle %69 uyuşuyor ve ayrışmaların hiçbiri elimizdeki
    veriyle kapatılabilir cinsten değil. Bir hisseyi yanlışlıkla "uygun değil"
    damgalamak, "değerlendirilmedi" bırakmaktan çok daha zararlıdır.
    """
    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    yazilan = 0
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
        stock.katilim_detail = _panel_metni(stock, sonuc)
        if sonuc["debt_ratio"] is not None:
            yazilan += 1

    db.commit()
    print(f"[Katılım] Tarama tamamlandı: {yazilan}/{len(stocks)} hissede oran hesaplandı.")
    return {"hesaplanan": yazilan, "toplam": len(stocks)}
