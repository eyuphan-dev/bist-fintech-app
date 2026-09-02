"""
custom_indicator.py
--------------------
Kullanıcının kendi formülünü (ör. "close - sma(20)") grafiğe gösterge
olarak ekleyebilmesini sağlar -- TradingView'ın Pine Script'inin çok
basitleştirilmiş, güvenli bir karşılığı.

GÜVENLİK -- NEDEN eval()/exec() KULLANILMADI
---------------------------------------------
Kullanıcıdan gelen bir string'i sunucuda `eval()`/`exec()` ile çalıştırmak
uzaktan kod çalıştırma (RCE) açığı demektir -- kullanıcı `__import__('os')`
gibi bir "formül" yazıp sunucuda keyfi kod çalıştırabilirdi.

Bunun yerine formül Python'un `ast` modülüyle SADECE AYRIŞTIRILIR (hiç
çalıştırılmaz), sonra kendi yazdığımız yorumlayıcı (_hesapla) bu ayrıştırılmış
ağacı DOLAŞIR ve her düğüm tipini elle tanır. Beyaz listede OLMAYAN hiçbir
şey (öznitelik erişimi, indeksleme, lambda, import, fonksiyon tanımı,
liste/sözlük, isim çözümlemesi dışındaki her şey) tanınmaz ve reddedilir.
Bu "varsayılan reddet" (default-deny) tasarım, yeni bir Python sürümünün
AST'sine yeni bir düğüm tipi eklemesi durumunda bile güvenli kalır --
tanınmayan her düğüm otomatik olarak hata verir, İZİN VERMEZ.

Beyaz liste:
  Değişkenler : open, high, low, close, volume
  İşlemler    : + - * / (ikili), tekli -
  Fonksiyonlar: sma(n), ema(n), rsi(n)  -- n=periyot, close üzerinden hesaplanır
                abs(x), min(a,b), max(a,b)
  Sabitler    : yalnızca sayısal (int/float)

sma/ema/rsi'nin matematiği backtest.py'deki DOĞRULANMIŞ fonksiyonlardan
alınır -- burada ikinci kez yazılıp farklı bir yuvarlama/sonuç üretme
riski alınmaz.
"""

from __future__ import annotations

import ast
from datetime import date, timedelta
from typing import Any, Dict, List

import numpy as np
from sqlalchemy.orm import Session

import models
from constants import HISTORY_RANGE_DAYS
from backtest import _sma_serisi, _ema_serisi, _rsi_serisi

_DEGISKENLER = {"open", "high", "low", "close", "volume"}
_MAKS_PERIYOT = 500
_MAKS_FORMUL_UZUNLUGU = 200


class FormulHatasi(Exception):
    """Formülde izin verilmeyen/anlaşılmayan bir şey bulunduğunda fırlatılır."""


def _hesapla(node: ast.AST, veri: Dict[str, np.ndarray], n: int) -> np.ndarray:
    if isinstance(node, ast.Expression):
        return _hesapla(node.body, veri, n)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise FormulHatasi("Yalnızca sayısal sabitler kullanılabilir.")
        return np.full(n, float(node.value))

    if isinstance(node, ast.Name):
        if node.id not in veri:
            raise FormulHatasi(f"Bilinmeyen değişken: '{node.id}'. Kullanılabilir: open, high, low, close, volume.")
        return veri[node.id]

    if isinstance(node, ast.BinOp):
        sol = _hesapla(node.left, veri, n)
        sag = _hesapla(node.right, veri, n)
        if isinstance(node.op, ast.Add):
            return sol + sag
        if isinstance(node.op, ast.Sub):
            return sol - sag
        if isinstance(node.op, ast.Mult):
            return sol * sag
        if isinstance(node.op, ast.Div):
            # Sıfıra bölme hatasız None'a düşürülür -- exception fırlatmak
            # tüm seriyi çöpe atmak yerine sadece o noktayı boş bırakmalı.
            return np.where(sag != 0, sol / np.where(sag == 0, 1.0, sag), np.nan)
        raise FormulHatasi("Desteklenmeyen işlem. Yalnızca + - * / kullanılabilir.")

    if isinstance(node, ast.UnaryOp):
        deger = _hesapla(node.operand, veri, n)
        if isinstance(node.op, ast.USub):
            return -deger
        if isinstance(node.op, ast.UAdd):
            return deger
        raise FormulHatasi("Desteklenmeyen tekli işlem.")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FormulHatasi("Geçersiz fonksiyon çağrısı.")
        ad = node.func.id
        if node.keywords:
            raise FormulHatasi("Anahtar kelime argümanı desteklenmiyor.")

        if ad in ("sma", "ema", "rsi"):
            if len(node.args) != 1:
                raise FormulHatasi(f"{ad}(periyot) tek bir sayı argümanı alır, örn. {ad}(20).")
            parg = node.args[0]
            if not (isinstance(parg, ast.Constant) and isinstance(parg.value, (int, float)) and not isinstance(parg.value, bool)):
                raise FormulHatasi(f"{ad} için periyot sabit bir sayı olmalı, örn. {ad}(20).")
            periyot = int(parg.value)
            if periyot < 1 or periyot > _MAKS_PERIYOT:
                raise FormulHatasi(f"Periyot 1-{_MAKS_PERIYOT} arasında olmalı.")
            kapanis = veri["close"].tolist()
            if ad == "sma":
                ham = _sma_serisi(kapanis, periyot)
            elif ad == "ema":
                ham = _ema_serisi(kapanis, periyot)
            else:
                ham = _rsi_serisi(kapanis, periyot)
            return np.array([float(x) if x is not None else np.nan for x in ham])

        if ad == "abs":
            if len(node.args) != 1:
                raise FormulHatasi("abs(x) tek argüman alır.")
            return np.abs(_hesapla(node.args[0], veri, n))

        if ad in ("min", "max"):
            if len(node.args) != 2:
                raise FormulHatasi(f"{ad}(a, b) iki argüman alır.")
            a = _hesapla(node.args[0], veri, n)
            b = _hesapla(node.args[1], veri, n)
            return np.minimum(a, b) if ad == "min" else np.maximum(a, b)

        raise FormulHatasi(f"Bilinmeyen fonksiyon: '{ad}'. Kullanılabilir: sma, ema, rsi, abs, min, max.")

    raise FormulHatasi(f"İzin verilmeyen ifade türü: {type(node).__name__}")


def compute_custom_formula(db: Session, symbol: str, range_code: str, formula: str) -> Dict[str, Any]:
    range_code = (range_code or "").upper()
    if range_code == "1D" or range_code not in HISTORY_RANGE_DAYS:
        return {"available": False, "reason": "Özel formül yalnızca günlük barlı aralıklarda (1H/1A/1Y/5Y) çalışır."}

    formula = (formula or "").strip()
    if not formula:
        return {"available": False, "reason": "Formül boş olamaz."}
    if len(formula) > _MAKS_FORMUL_UZUNLUGU:
        return {"available": False, "reason": f"Formül çok uzun (en fazla {_MAKS_FORMUL_UZUNLUGU} karakter)."}

    try:
        agac = ast.parse(formula, mode="eval")
    except SyntaxError:
        return {"available": False, "reason": "Formül ayrıştırılamadı. Örnek: close - sma(20)"}

    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        return {"available": False, "reason": "Hisse bulunamadı."}

    cutoff = date.today() - timedelta(days=HISTORY_RANGE_DAYS[range_code])
    isinma_gun = 260
    bars = (
        db.query(models.StockPriceDaily)
        .filter(models.StockPriceDaily.stock_id == stock.id)
        .order_by(models.StockPriceDaily.trade_date.asc())
        .all()
    )
    if len(bars) < 30:
        return {"available": False, "reason": "Bu hisse için yeterli günlük geçmiş yok."}

    kirpma_index = 0
    for i, b in enumerate(bars):
        if b.trade_date >= cutoff:
            kirpma_index = max(0, i - isinma_gun)
            break
    hesap_bars = bars[kirpma_index:]
    n = len(hesap_bars)

    veri = {
        "open": np.array([float(b.open) if b.open is not None else float(b.close) for b in hesap_bars]),
        "high": np.array([float(b.high) if b.high is not None else float(b.close) for b in hesap_bars]),
        "low": np.array([float(b.low) if b.low is not None else float(b.close) for b in hesap_bars]),
        "close": np.array([float(b.close) for b in hesap_bars]),
        "volume": np.array([float(b.volume) if b.volume is not None else 0.0 for b in hesap_bars]),
    }
    dates = [b.trade_date for b in hesap_bars]

    try:
        sonuc = _hesapla(agac, veri, n)
    except FormulHatasi as e:
        return {"available": False, "reason": str(e)}
    except ZeroDivisionError:
        return {"available": False, "reason": "Sıfıra bölme hatası."}
    except Exception:
        # Beklenmeyen bir sayisal hata (or. asiri buyuk periyot) -- kullaniciya
        # yigin izini degil, genel bir mesaj gosterilir.
        return {"available": False, "reason": "Formül hesaplanamadı. Söz dizimini kontrol edin."}

    sonuc = np.asarray(sonuc, dtype=float)
    if sonuc.shape != (n,):
        sonuc = np.broadcast_to(sonuc, (n,)).copy()

    baslangic = next((i for i, d in enumerate(dates) if d >= cutoff), 0)
    degerler: List[Any] = [
        None if (np.isnan(v) or np.isinf(v)) else round(float(v), 4) for v in sonuc[baslangic:]
    ]

    return {
        "available": True,
        "dates": [d.isoformat() for d in dates[baslangic:]],
        "values": degerler,
    }
