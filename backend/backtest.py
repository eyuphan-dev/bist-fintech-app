"""
backtest.py
-----------
Strateji geri testi — bir kuralın geçmişte ne yapacağını ölçer.

Ücretli platformların (Matriks Prime, Fintables) paket içinde sunduğu özelliğin
karşılığı. Veri zaten bizde: stock_prices_daily'de 2021'den bu yana günlük
OHLCV var.

DÜRÜSTLÜK KURALLARI — bir geri test kolayca yalan söyler, o yüzden:

1. GELECEĞE BAKMA YOK. Sinyal t günü KAPANIŞIYLA hesaplanır, işlem t+1 günü
   AÇILIŞINDA yapılır. Sinyalin oluştuğu mumun kapanışından alım yapmak,
   gerçekte mümkün olmayan bir fiyattan işlem varsaymak olurdu ve sonucu
   sistematik olarak güzelleştirirdi.

2. İŞLEM MALİYETİ VAR. Komisyon varsayılan olarak uygulanır. Maliyetsiz geri
   test, çok işlem yapan stratejileri olduğundan çok daha iyi gösterir.

3. AL-TUT KARŞILAŞTIRMASI ZORUNLU. "%40 kazandırdı" tek başına anlamsızdır;
   aynı dönemde hisse zaten %60 yükseldiyse strateji para KAYBETTİRMİŞTİR.

4. TAM POZİSYON. Kısmi alım, kaldıraç veya açığa satış yoktur; nakit boşta
   beklerken hiçbir getiri üretmez.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

import models

# Komisyon oranı constants.py'den gelir — simülatördeki gerçek AL/SAT ile
# backtest'in AYNI oranı kullanması şart. Ayrı tanımlansalardı zamanla
# birbirinden sapar ve backtest sonucu gerçek işlemle kıyaslanamaz hale gelirdi.
# Sıfır varsaymak ise çok işlem yapan stratejileri haksız yere kayırırdı.
from constants import KOMISYON_ORANI_PCT

VARSAYILAN_KOMISYON_PCT = KOMISYON_ORANI_PCT

STRATEJILER = {
    "RSI": {
        "label": "RSI Aşırı Satım / Aşırı Alım",
        "description": "RSI eşiğin altına düşünce al, üst eşiği aşınca sat.",
        "params": {"period": 14, "buy_below": 30, "sell_above": 70},
    },
    "SMA_CROSS": {
        "label": "Hareketli Ortalama Kesişimi",
        "description": "Kısa ortalama uzun ortalamayı yukarı keserse al, aşağı keserse sat.",
        "params": {"fast": 20, "slow": 50},
    },
    "MACD": {
        "label": "MACD Sinyal Kesişimi",
        "description": "MACD çizgisi sinyal çizgisini yukarı keserse al, aşağı keserse sat.",
        "params": {"fast": 12, "slow": 26, "signal": 9},
    },
}


# ---------------------------------------------------------------------------
# Göstergeler — tam seri döndürürler (her gün için bir değer veya None)
# ---------------------------------------------------------------------------
def _rsi_serisi(closes: list[float], period: int) -> list[Optional[float]]:
    """Wilder yumuşatmalı RSI. İlk `period` gün için None döner."""
    out: list[Optional[float]] = [None] * len(closes)
    if len(closes) <= period:
        return out

    kazanclar = kayiplar = 0.0
    for i in range(1, period + 1):
        fark = closes[i] - closes[i - 1]
        kazanclar += max(fark, 0.0)
        kayiplar += max(-fark, 0.0)
    ort_kazanc, ort_kayip = kazanclar / period, kayiplar / period

    def rsi_hesapla(k: float, z: float) -> float:
        if z == 0:
            return 100.0
        rs = k / z
        return 100.0 - (100.0 / (1.0 + rs))

    out[period] = rsi_hesapla(ort_kazanc, ort_kayip)
    for i in range(period + 1, len(closes)):
        fark = closes[i] - closes[i - 1]
        ort_kazanc = (ort_kazanc * (period - 1) + max(fark, 0.0)) / period
        ort_kayip = (ort_kayip * (period - 1) + max(-fark, 0.0)) / period
        out[i] = rsi_hesapla(ort_kazanc, ort_kayip)
    return out


def _sma_serisi(closes: list[float], period: int) -> list[Optional[float]]:
    out: list[Optional[float]] = [None] * len(closes)
    if len(closes) < period:
        return out
    toplam = sum(closes[:period])
    out[period - 1] = toplam / period
    for i in range(period, len(closes)):
        toplam += closes[i] - closes[i - period]
        out[i] = toplam / period
    return out


def _ema_serisi(values: list[float], period: int) -> list[Optional[float]]:
    out: list[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    onceki = sum(values[:period]) / period
    out[period - 1] = onceki
    for i in range(period, len(values)):
        onceki = values[i] * k + onceki * (1 - k)
        out[i] = onceki
    return out


def _macd_serisi(closes: list[float], fast: int, slow: int, signal: int):
    hizli, yavas = _ema_serisi(closes, fast), _ema_serisi(closes, slow)
    macd: list[Optional[float]] = [
        (h - y) if (h is not None and y is not None) else None for h, y in zip(hizli, yavas)
    ]
    # Sinyal çizgisi MACD'nin EMA'sıdır; MACD'nin None olmayan kısmından hesaplanır.
    ilk = next((i for i, v in enumerate(macd) if v is not None), None)
    sinyal: list[Optional[float]] = [None] * len(closes)
    if ilk is not None:
        gecerli = [v for v in macd[ilk:] if v is not None]
        s = _ema_serisi(gecerli, signal)
        for i, v in enumerate(s):
            sinyal[ilk + i] = v
    return macd, sinyal


# ---------------------------------------------------------------------------
def _sinyaller(strateji: str, closes: list[float], params: dict) -> list[Optional[str]]:
    """Her gün için 'AL' / 'SAT' / None döner. Gün t'nin KAPANIŞ verisini kullanır."""
    n = len(closes)
    out: list[Optional[str]] = [None] * n

    if strateji == "RSI":
        p = int(params.get("period", 14))
        alt = float(params.get("buy_below", 30))
        ust = float(params.get("sell_above", 70))
        rsi = _rsi_serisi(closes, p)
        for i in range(1, n):
            onceki, simdi = rsi[i - 1], rsi[i]
            if onceki is None or simdi is None:
                continue
            # KESİŞİM aranır, seviye değil: RSI 25'te on gün kalırsa bu tek bir
            # alım sinyalidir, on tane değil.
            if onceki >= alt and simdi < alt:
                out[i] = "AL"
            elif onceki <= ust and simdi > ust:
                out[i] = "SAT"

    elif strateji == "SMA_CROSS":
        f, s = int(params.get("fast", 20)), int(params.get("slow", 50))
        hizli, yavas = _sma_serisi(closes, f), _sma_serisi(closes, s)
        for i in range(1, n):
            if None in (hizli[i], yavas[i], hizli[i - 1], yavas[i - 1]):
                continue
            if hizli[i - 1] <= yavas[i - 1] and hizli[i] > yavas[i]:
                out[i] = "AL"
            elif hizli[i - 1] >= yavas[i - 1] and hizli[i] < yavas[i]:
                out[i] = "SAT"

    elif strateji == "MACD":
        macd, sinyal = _macd_serisi(
            closes, int(params.get("fast", 12)), int(params.get("slow", 26)), int(params.get("signal", 9))
        )
        for i in range(1, n):
            if None in (macd[i], sinyal[i], macd[i - 1], sinyal[i - 1]):
                continue
            if macd[i - 1] <= sinyal[i - 1] and macd[i] > sinyal[i]:
                out[i] = "AL"
            elif macd[i - 1] >= sinyal[i - 1] and macd[i] < sinyal[i]:
                out[i] = "SAT"

    return out


def _maks_dusus(seri: list[float]) -> float:
    """En yüksek tepeden en derin dibe yüzde düşüş."""
    zirve = seri[0] if seri else 0.0
    en_kotu = 0.0
    for v in seri:
        zirve = max(zirve, v)
        if zirve > 0:
            en_kotu = min(en_kotu, (v - zirve) / zirve * 100)
    return round(en_kotu, 2)


def run_backtest(
    db: Session,
    symbol: str,
    strategy: str,
    *,
    years: int = 3,
    initial_capital: float = 100_000.0,
    commission_pct: float = VARSAYILAN_KOMISYON_PCT,
    params: Optional[dict] = None,
) -> dict[str, Any]:
    strategy = (strategy or "").upper()
    if strategy not in STRATEJILER:
        return {"ok": False, "error": "Bilinmeyen strateji."}

    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return {"ok": False, "error": "Hisse bulunamadı."}

    bars = (
        db.query(models.StockPriceDaily)
        .filter_by(stock_id=stock.id)
        .order_by(models.StockPriceDaily.trade_date.asc())
        .all()
    )
    if len(bars) < 120:
        return {"ok": False, "error": "Bu hisse için yeterli günlük geçmiş yok (en az 120 iş günü gerekir)."}

    # Yıl kırpması EN SONDAN yapılır ama göstergeler için ısınma payı bırakılır:
    # 3 yıllık testte 200 günlük ortalama, testin ilk gününde hazır olmalıdır.
    hedef = min(len(bars), years * 252)
    isinma = min(250, len(bars) - hedef)
    dilim = bars[len(bars) - hedef - isinma :]
    baslangic_index = isinma

    closes = [float(b.close) for b in dilim]
    # Açılış bazı günlerde boş olabilir; o gün kapanış kullanılır.
    opens = [float(b.open) if b.open is not None else float(b.close) for b in dilim]
    tarihler = [b.trade_date for b in dilim]

    p = dict(STRATEJILER[strategy]["params"])
    if params:
        p.update({k: v for k, v in params.items() if v is not None})
    sinyal = _sinyaller(strategy, closes, p)

    nakit = initial_capital
    adet = 0.0
    islemler: list[dict] = []
    ozkaynak: list[float] = []
    ozkaynak_tarih: list[date] = []
    alis_fiyati = 0.0
    kom = commission_pct / 100.0

    for i in range(baslangic_index, len(dilim)):
        # GELECEĞE BAKMA ENGELİ: bugünün işlemi DÜNÜN sinyaliyle, bugünün
        # açılışından yapılır.
        emir = sinyal[i - 1] if i > 0 else None
        fiyat = opens[i]

        if emir == "AL" and adet == 0 and fiyat > 0:
            alinabilir = nakit / (fiyat * (1 + kom))
            if alinabilir > 0:
                adet = alinabilir
                nakit = 0.0
                alis_fiyati = fiyat
                islemler.append({
                    "date": tarihler[i], "action": "AL", "price": round(fiyat, 2), "pnl_pct": None,
                })
        elif emir == "SAT" and adet > 0 and fiyat > 0:
            nakit = adet * fiyat * (1 - kom)
            getiri = (fiyat - alis_fiyati) / alis_fiyati * 100 if alis_fiyati else 0.0
            islemler.append({
                "date": tarihler[i], "action": "SAT", "price": round(fiyat, 2), "pnl_pct": round(getiri, 2),
            })
            adet = 0.0

        ozkaynak.append(nakit + adet * closes[i])
        ozkaynak_tarih.append(tarihler[i])

    if not ozkaynak:
        return {"ok": False, "error": "Test aralığında veri bulunamadı."}

    # Açık pozisyon son kapanışla değerlenir; zorla kapatılmaz çünkü strateji
    # hâlâ pozisyonda olmayı söylüyor.
    son_deger = ozkaynak[-1]
    strateji_getiri = (son_deger - initial_capital) / initial_capital * 100

    ilk_fiyat = closes[baslangic_index]
    al_tut_seri = [initial_capital * (c / ilk_fiyat) for c in closes[baslangic_index:]]
    al_tut_getiri = (al_tut_seri[-1] - initial_capital) / initial_capital * 100

    kapanan = [t for t in islemler if t["action"] == "SAT"]
    kazanan = sum(1 for t in kapanan if (t["pnl_pct"] or 0) > 0)

    # Grafik için örnekleme: 5 yıllık seride ~1250 nokta gereksiz.
    adim = max(1, len(ozkaynak) // 180)
    egri = [
        {
            "date": ozkaynak_tarih[i],
            "strategy": round(ozkaynak[i], 2),
            "buy_hold": round(al_tut_seri[i], 2),
        }
        for i in range(0, len(ozkaynak), adim)
    ]
    if egri and egri[-1]["date"] != ozkaynak_tarih[-1]:
        egri.append({
            "date": ozkaynak_tarih[-1],
            "strategy": round(ozkaynak[-1], 2),
            "buy_hold": round(al_tut_seri[-1], 2),
        })

    return {
        "ok": True,
        "symbol": stock.symbol,
        "company_name": stock.company_name,
        "strategy": strategy,
        "strategy_label": STRATEJILER[strategy]["label"],
        "params": p,
        "start_date": ozkaynak_tarih[0],
        "end_date": ozkaynak_tarih[-1],
        "initial_capital": initial_capital,
        "final_value": round(son_deger, 2),
        "strategy_return_pct": round(strateji_getiri, 2),
        "buy_hold_return_pct": round(al_tut_getiri, 2),
        "excess_return_pct": round(strateji_getiri - al_tut_getiri, 2),
        "trade_count": len(islemler),
        "closed_trades": len(kapanan),
        "win_count": kazanan,
        "win_rate": round(kazanan / len(kapanan) * 100, 1) if kapanan else None,
        "max_drawdown_pct": _maks_dusus(ozkaynak),
        "buy_hold_max_drawdown_pct": _maks_dusus(al_tut_seri),
        "commission_pct": commission_pct,
        "in_position": adet > 0,
        "equity_curve": egri,
        "trades": islemler[-20:],
    }
