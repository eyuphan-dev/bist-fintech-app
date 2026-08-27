"""
dividend_stability.py
----------------------
Temettü ödeme geçmişinden İSTİKRAR SINIFI çıkarır.

NEDEN NUMERİK BİR "SKOR" DEĞİL: `katilim.py`de yaşanan hatadan ders alındı —
oradaki `purification_rate` yer tutucu, ikişerli tekrar eden yuvarlak sayılardı
ve gerçek bir endeks metodolojisine dayanmıyordu (bkz. projem.md §12). Burada
durum FARKLI: girdi (yıllık temettü toplamları) tamamen gerçek ve yfinance'tan
gelen `dividend_history` tablosundan hesaplanıyor, uydurma değer yok. Yine de
gizli ağırlıklı bir "0-100 skor" yerine ŞEFFAF, tek tek doğrulanabilir
metrikler + bunlardan AÇIKÇA türetilen bir sınıf döndürülür. Kullanıcı
"neden B sınıfı" sorusuna her zaman metriklere bakarak cevap bulabilmeli.

Yöntem, ABD'de "Dividend Aristocrats/Kings" sınıflandırmasında kullanılan
yerleşik kavramlara dayanır: kesintisiz ödeme serisi, kesintisiz artış serisi,
tarihte kesinti olup olmadığı.
"""

from typing import Dict, Optional, TypedDict


class DividendStability(TypedDict):
    complete_years: int              # hesaba katılan tamamlanmış yıl sayısı
    consecutive_paid_years: int      # en son tam yıldan geriye, kesintisiz ödeme
    consecutive_increase_years: int  # en son tam yıldan geriye, azalmayan artış
    ever_cut: bool                   # tarihte herhangi bir yıl ödeme SIFIRA düştü mü
    cut_years: int                   # kesinti sayısı (aralıktaki sıfır/eksik yıl)
    stability_class: Optional[str]   # "A" / "B" / "C" / "D" / None (veri yok)
    stability_label: str             # kullanıcıya gösterilecek Türkçe açıklama


def compute_dividend_stability(
    yearly_totals: Dict[int, float],
    current_year: int,
    min_years_required: int = 3,
) -> DividendStability:
    """
    `yearly_totals`: {yıl: o yılki toplam temettü} — içinde bulunulan yıl
    DAHİL OLABİLİR ama burada HARİÇ TUTULUR; yıl bitmeden düşük toplam
    "kesinti" gibi görünüp yanlış sınıf üretirdi (dividend-history ucundaki
    aynı ilkeyle tutarlı, bkz. main.py get_dividend_history).
    """
    tamamlanan = sorted((y for y in yearly_totals if y < current_year), reverse=True)

    if len(tamamlanan) < min_years_required:
        return DividendStability(
            complete_years=len(tamamlanan),
            consecutive_paid_years=0,
            consecutive_increase_years=0,
            ever_cut=False,
            cut_years=0,
            stability_class=None,
            stability_label=f"Sınıflandırma için en az {min_years_required} tam yıllık veri gerekir "
                             f"(mevcut: {len(tamamlanan)}).",
        )

    en_yeni = tamamlanan[0]
    en_eski = tamamlanan[-1]

    # Kesintisiz ödeme serisi: en_yeni'den geriye, ARDIŞIK yıl numarası VE
    # pozitif ödeme şartlarının ikisi de sağlanmalı. Bir yıl atlanmışsa
    # (örn. 2019 var ama 2018 yoksa) o da kesinti sayılır.
    kesintisiz = 0
    for i, yil in enumerate(tamamlanan):
        beklenen_yil = en_yeni - i
        if yil == beklenen_yil and yearly_totals.get(yil, 0) > 0:
            kesintisiz += 1
        else:
            break

    # Aralıktaki TÜM yıllar taranarak kesinti sayısı bulunur (yalnızca en
    # yeni seriden değil, tüm geçmişten) — "hiç kesinti oldu mu" sorusu bu.
    tum_yillar = range(en_eski, en_yeni + 1)
    kesinti_sayisi = sum(1 for y in tum_yillar if yearly_totals.get(y, 0) <= 0)

    # Artış serisi: en_yeni'den geriye, her yıl bir ÖNCEKİNDEN (yani
    # kronolojik olarak daha eski olandan) KÜÇÜK OLMAMALI. tamamlanan listesi
    # yeni->eski sıralı olduğu için vals[i] >= vals[i+1] karşılaştırılır.
    vals = [yearly_totals.get(y, 0.0) for y in tamamlanan]
    artis_serisi = 0
    for i in range(len(vals) - 1):
        if vals[i] >= vals[i + 1] and vals[i + 1] > 0:
            artis_serisi += 1
        else:
            break

    # Sınıflandırma kuralı — SABİT VE AÇIK, gizli ağırlık yok:
    if kesinti_sayisi == 0 and kesintisiz >= 10:
        sinif, etiket = "A", f"{kesintisiz} yıldır kesintisiz ödeme, hiç kesinti yok."
    elif kesinti_sayisi <= 1 and kesintisiz >= 5:
        sinif, etiket = "B", f"Son {kesintisiz} yıl kesintisiz, geçmişte {kesinti_sayisi} kesinti."
    elif kesintisiz >= 1:
        sinif, etiket = "C", f"Son ödeme yapıldı ama seri kısa ({kesintisiz} yıl) veya geçmişte {kesinti_sayisi} kesinti var."
    else:
        sinif, etiket = "D", f"Son tamamlanmış yılda ({en_yeni}) ödeme yapılmadı."

    return DividendStability(
        complete_years=len(tamamlanan),
        consecutive_paid_years=kesintisiz,
        consecutive_increase_years=artis_serisi,
        ever_cut=kesinti_sayisi > 0,
        cut_years=kesinti_sayisi,
        stability_class=sinif,
        stability_label=etiket,
    )
