"""
report_pdf.py
--------------
Kullanıcının portföy karnesini indirilebilir bir PDF'e döker.

Hiçbir yeni hesaplama YAPMAZ -- zaten var olan `/api/portfolio` ve
`/api/portfolio/scorecard` uçlarının ÇIKTISINI (dict/Pydantic model) girdi
olarak alır, yalnızca biçimlendirir. Böylece rapordaki rakamlar uygulamanın
geri kalanıyla HER ZAMAN birebir tutarlı kalır -- ikinci bir hesaplama
yolu icat edilip zamanla sapması riski yoktur.
"""

import os
from datetime import datetime
from io import BytesIO
from typing import Any, Dict

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Standart PDF fontları (Helvetica vb.) WinAnsi kodlamasını kullanır ve
# Türkçe'ye özgü ı/İ/ş/Ş/ğ/Ğ karakterleri YOKTUR -- bu harfler PDF'te kare
# olarak basılır (ölçüldü: "Kullanıcı" -> "Kullan■c■"). reportlab'ın kendi
# paketiyle birlikte gelen Vera (Bitstream Vera Sans) fontu bu karakterlerin
# TAMAMINI destekliyor (test edildi: İıŞşĞğÇçÖöÜü hepsi doğru basıldı) --
# ayrı bir font dosyası indirip repoya eklemeye gerek kalmadı.
_FONT_DIZINI = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
pdfmetrics.registerFont(TTFont("Vera", os.path.join(_FONT_DIZINI, "Vera.ttf")))
pdfmetrics.registerFont(TTFont("Vera-Bold", os.path.join(_FONT_DIZINI, "VeraBd.ttf")))
# <b>...</b> gibi Paragraph içi işaretlemenin "Vera-Bold"a düşmesi için --
# aksi halde reportlab bilinmeyen bir aile için varsayılan Helvetica-Bold'a
# düşer ve kalın metin yine kare basardı.
pdfmetrics.registerFontFamily("Vera", normal="Vera", bold="Vera-Bold", italic="Vera", boldItalic="Vera-Bold")

_KOYU = colors.HexColor("#151921")
_GRI = colors.HexColor("#555555")
_ACIK_GRI = colors.HexColor("#F5F5F5")
_YESIL = colors.HexColor("#0F9D6E")
_KIRMIZI = colors.HexColor("#D6365F")


def _tl(v: float) -> str:
    return f"{v:,.2f} TL".replace(",", "X").replace(".", ",").replace("X", ".")


def _yuzde_rengi(v: float):
    return _YESIL if v >= 0 else _KIRMIZI


def build_portfolio_report_pdf(username: str, portfolio: Dict[str, Any], scorecard: Dict[str, Any]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    for stil_adi in ("Normal", "Title", "Heading2"):
        styles[stil_adi].fontName = "Vera"
    baslik = ParagraphStyle("Baslik", parent=styles["Title"], fontName="Vera-Bold", fontSize=18, alignment=TA_LEFT, textColor=_KOYU)
    alt_baslik = ParagraphStyle("AltBaslik", parent=styles["Heading2"], fontName="Vera-Bold", fontSize=13, spaceBefore=16, spaceAfter=6, textColor=_KOYU)
    normal = styles["Normal"]

    elems = []
    elems.append(Paragraph("BIST Simülasyonu — Portföy Raporu", baslik))
    elems.append(Paragraph(
        f"Kullanıcı: <b>{username}</b> &nbsp;·&nbsp; Oluşturulma: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        normal,
    ))
    elems.append(Spacer(1, 0.6 * cm))

    # --- Özet ---
    elems.append(Paragraph("Özet", alt_baslik))
    getiri_pct = portfolio["profit_loss_pct"]
    ozet_satirlari = [
        ["Toplam Portföy Değeri", _tl(portfolio["total_portfolio_value"])],
        ["Nakit Bakiye", _tl(portfolio["balance"])],
        # {:+.2f} kullanılır, "'+' if x>=0" DEĞİL: round(-0.001, 2) Python'da
        # -0.0 üretir ve -0.0 >= 0 True döner -- "+" ile birleşince "+-0.00%"
        # gibi çift işaretli, yanlış bir sonuç çıkardı (ölçüldü).
        ["Toplam Getiri", f"{getiri_pct:+.2f}%"],
        ["Açık Pozisyon Sayısı", str(len(portfolio["items"]))],
    ]
    ozet_tablo = Table(ozet_satirlari, colWidths=[8 * cm, 7 * cm])
    ozet_tablo.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Vera"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TEXTCOLOR", (0, 0), (0, -1), _GRI),
        ("FONTNAME", (1, 0), (1, -1), "Vera-Bold"),
        ("TEXTCOLOR", (1, 2), (1, 2), _yuzde_rengi(getiri_pct)),
    ]))
    elems.append(ozet_tablo)

    # --- Açık pozisyonlar ---
    elems.append(Paragraph("Açık Pozisyonlar", alt_baslik))
    if portfolio["items"]:
        basliklar = ["Sembol", "Adet", "Ort. Maliyet", "Güncel Fiyat", "Değer", "K/Z %"]
        satirlar = [basliklar]
        for it in portfolio["items"]:
            satirlar.append([
                it["symbol"],
                f"{it['quantity']:,.2f}",
                f"{it['average_cost']:,.2f}",
                f"{it['current_price']:,.2f}",
                f"{it['current_value']:,.2f}",
                f"{it['profit_loss_pct']:+.2f}%",
            ])
        tablo = Table(satirlar, colWidths=[2.3 * cm, 2.2 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.1 * cm], repeatRows=1)
        stil = [
            ("FONTNAME", (0, 0), (-1, -1), "Vera"),
            ("BACKGROUND", (0, 0), (-1, 0), _KOYU),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Vera-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ACIK_GRI]),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ]
        for i, it in enumerate(portfolio["items"], start=1):
            stil.append(("TEXTCOLOR", (5, i), (5, i), _yuzde_rengi(it["profit_loss_pct"])))
        tablo.setStyle(TableStyle(stil))
        elems.append(tablo)
    else:
        elems.append(Paragraph("Şu an açık pozisyon yok.", normal))

    # --- Performans karnesi (gerçekleşen işlemler) ---
    elems.append(Paragraph("Performans Karnesi (gerçekleşen işlemler)", alt_baslik))
    if scorecard.get("has_data"):
        realized = scorecard["realized_pnl"]
        karne_satirlari = [
            ["Gerçekleşen Kâr/Zarar", _tl(realized)],
            ["Satış Sayısı", str(scorecard["sell_count"])],
            ["İsabet Oranı", f"%{scorecard['win_rate']}" if scorecard.get("win_rate") is not None else "—"],
            ["Ortalama Tutma Süresi", f"{scorecard['avg_holding_days']} gün" if scorecard.get("avg_holding_days") is not None else "—"],
        ]
        if scorecard.get("best_trade"):
            karne_satirlari.append(["En İyi İşlem", f"{scorecard['best_trade']['symbol']} ({_tl(scorecard['best_trade']['pnl'])})"])
        if scorecard.get("worst_trade"):
            karne_satirlari.append(["En Kötü İşlem", f"{scorecard['worst_trade']['symbol']} ({_tl(scorecard['worst_trade']['pnl'])})"])

        karne_tablo = Table(karne_satirlari, colWidths=[8 * cm, 7 * cm])
        karne_tablo.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Vera"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TEXTCOLOR", (0, 0), (0, -1), _GRI),
            ("FONTNAME", (1, 0), (1, -1), "Vera-Bold"),
            ("TEXTCOLOR", (1, 0), (1, 0), _yuzde_rengi(realized)),
        ]))
        elems.append(karne_tablo)
    else:
        elems.append(Paragraph("Henüz gerçekleşmiş (satılmış) bir işlem yok.", normal))

    elems.append(Spacer(1, 1 * cm))
    yasal_stil = ParagraphStyle("Yasal", parent=normal, fontSize=7, textColor=colors.grey)
    elems.append(Paragraph(
        "Bu rapor yatırım tavsiyesi değildir. Uygulama gerçek para kullanmaz, "
        "veriler en az 15 dakika gecikmelidir. BIST Simülasyonu &amp; Yapay Zeka Trader.",
        yasal_stil,
    ))

    doc.build(elems)
    return buffer.getvalue()
