# -*- coding: utf-8 -*-
"""
smoke_test.py — uygulamanin HER ozelligini tek tek calistiran duman testi.

CALISTIRMA
    # once yerel backend ayakta olmali:
    #   ./venv/Scripts/python.exe -m uvicorn main:app --port 4000
    ./venv/Scripts/python.exe smoke_test.py

NE YAPAR
    90 test: kimlik, hisse/piyasa, grafik, analiz, backtest, haber, kurumsal
    veri, portfoy, islem, bekleyen emir, bot, favori, topluluk, bildirim ve
    sinir/guvenlik kontrolleri.

NEDEN IKI HEDEF
    Salt-okunur uclar URETIME gider: bir ucun 200 donmesi yetmez, ICINDE VERI
    OLMASI da gerekir ve bunu ancak gercek veriyle anlarsin. Bu ayrim dort
    gercek arizayi ortaya cikardi: onemli pay sahibi haberleri 0 kayit, fon
    katalogu 3 fon, halka arz takvimi 0 kayit, hisse aramasi Turkce harf
    duyarli.

    Kimlik gerektiren ve YAZAN uclar YERELE gider; testin uretim
    veritabanina kullanici, islem ve yorum yazmasi kabul edilemez.

SONUC ISARETLERI
    [+] gecti   [X] hata   [!] uc calisiyor ama BOS veri donuyor

    [!] cikti mi koda degil VERI BORU HATTINA bak: uc dogru, besleyen
    zamanlanmis is ya da dis kaynak calismiyordur.

NOT: PROD sabiti canli siteye bakar; testler salt-okunurdur ama yine de
uretime istek atar. Cevrimdisi calisirken PROD'u LOCAL yapabilirsin.
"""
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

# CI MODU: --ci (ya da SMOKE_CI=1) verildiginde salt-okunur testler de YERELE
# yonlendirilir ve "veri bos" bulgulari BASARISIZLIK SAYILMAZ.
#
# Nedeni: CI'daki veritabani bostur (165 hisse tohumlanir, fiyat/haber/KAP
# verisi yoktur). Orada "fon sayisi >= 10" gibi bir sarti aramak, kodu degil
# veriyi test etmek olur. CI'in isi soezlesmeyi korumaktir: uc ayakta mi,
# dogru HTTP kodunu donuyor mu, kimlik ve dogrulama kurallari calisiyor mu.
# Veri bollugu ayri bir soru ve onu elle kosarak (PROD'a karsi) izliyoruz.
CI = "--ci" in sys.argv or os.getenv("SMOKE_CI") == "1"

LOCAL = os.getenv("SMOKE_LOCAL_URL", "http://127.0.0.1:4000")
PROD = LOCAL if CI else os.getenv("SMOKE_PROD_URL", "https://borsa-trader.duckdns.org")
sonuclar = []


def cagir(base, yol, yontem="GET", govde=None, token=None, timeout=40):
    url = base + yol
    data = json.dumps(govde).encode() if govde is not None else None
    req = urllib.request.Request(url, data=data, method=yontem)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                govde_json = json.loads(raw) if raw else None
            except Exception:
                govde_json = raw[:200].decode("utf-8", "replace")
            return r.status, govde_json, time.time() - t0
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            body = json.loads(raw)
        except Exception:
            body = raw[:200].decode("utf-8", "replace")
        return e.code, body, time.time() - t0
    except Exception as e:
        return 0, str(e), time.time() - t0


def kaydet(durum, ad, mesaj, sure=0.0):
    sonuclar.append((durum, ad, mesaj, sure))


def bekle(ad, kod_kumesi, base, yol, yontem="GET", **kw):
    """Belirli HTTP kodlarindan biri bekleniyor (reddedilmeli testleri icin)."""
    kod, g, sure = cagir(base, yol, yontem, **kw)
    tamam = kod in kod_kumesi
    kaydet("TAMAM" if tamam else "HATA", ad,
           "HTTP {}".format(kod) if tamam else "HTTP {} (beklenen {}) {}".format(kod, kod_kumesi, str(g)[:120]),
           sure)
    return g


def test(ad, base, yol, yontem="GET", **kw):
    beklenen = kw.pop("beklenen", 200)
    kontrol = kw.pop("kontrol", None)
    kod, govde, sure = cagir(base, yol, yontem, **kw)
    if kod != beklenen:
        kaydet("HATA", ad, "HTTP {} (beklenen {}) {}".format(kod, beklenen, str(govde)[:140]), sure)
        return govde
    if kontrol:
        try:
            mesaj = kontrol(govde)
        except Exception as e:
            mesaj = "kontrol patladi: {}".format(e)
        if mesaj:
            kaydet("BOS" if mesaj.startswith("bos") else "UYARI", ad, mesaj, sure)
            return govde
    n = "{} kayit".format(len(govde)) if isinstance(govde, list) else "ok"
    kaydet("TAMAM", ad, n, sure)
    return govde


def dolu(minimum=1, alan=None):
    def f(g):
        if g is None:
            return "bos: yanit None"
        if isinstance(g, list):
            if len(g) < minimum:
                return "bos: {} kayit ({} bekleniyordu)".format(len(g), minimum)
            if alan and g and isinstance(g[0], dict) and g[0].get(alan) is None:
                return "ilk kaydin '{}' alani None".format(alan)
        elif isinstance(g, dict):
            if alan and g.get(alan) is None:
                return "'{}' alani None".format(alan)
        return None
    return f


S = "THYAO"

# ---------- 1. KIMLIK ----------
rnd = "".join(random.choices(string.ascii_lowercase, k=8))
eposta = "test_{}@ornek.com".format(rnd)
sifre = "Deneme12345!"
kod, g, _ = cagir(LOCAL, "/api/auth/register", "POST",
                  {"username": "t" + rnd, "email": eposta, "password": sifre, "terms_accepted": True})
kaydet("TAMAM" if kod in (200, 201) else "HATA", "Kimlik: kayit ol", "HTTP {} {}".format(kod, str(g)[:110]))
kod, g, _ = cagir(LOCAL, "/api/auth/login", "POST", {"username": "t" + rnd, "password": sifre})
TOKEN = (g or {}).get("access_token") if kod == 200 else None
kaydet("TAMAM" if TOKEN else "HATA", "Kimlik: giris yap", "HTTP {} token={}".format(kod, "var" if TOKEN else "YOK"))
test("Kimlik: /auth/me", LOCAL, "/api/auth/me", token=TOKEN, kontrol=dolu(alan="email"))
bekle("Kimlik: tokensiz reddediliyor", (401, 403), LOCAL, "/api/auth/me")
bekle("Kimlik: yanlis sifre reddi", (400, 401), LOCAL, "/api/auth/login", "POST",
      govde={"username": "t" + rnd, "password": "yanlisSifre"})
bekle("Kimlik: ayni eposta ikinci kayit reddi", (400, 409), LOCAL, "/api/auth/register", "POST",
      govde={"username": "t" + rnd, "email": eposta, "password": sifre, "terms_accepted": True})

# ---------- 2. HISSE VE PIYASA ----------
test("Hisse: katalog", PROD, "/api/stocks", kontrol=dolu(100, "symbol"))
test("Tarayici: katilim filtresi", PROD, "/api/screener?katilim_only=true", kontrol=dolu(5))
test("Hisse: detay", PROD, "/api/stocks/{}".format(S), kontrol=dolu(alan="current_price"))
test("Hisse: arama", PROD, "/api/stocks/search?q=thy", kontrol=dolu(1))
test("Hisse: karsilastir", PROD, "/api/stocks/compare?symbols={},ASELS".format(S), kontrol=dolu(2))
for r in ("1D", "1W", "1M", "1Y", "5Y"):
    test("Grafik: gecmis {}".format(r), PROD, "/api/stocks/{}/history?range={}".format(S, r), kontrol=dolu(1))
test("Analiz: derin analiz", PROD, "/api/stocks/{}/analysis".format(S), kontrol=dolu(alan=None))
test("Analiz: bilanco", PROD, "/api/stocks/{}/financials".format(S), kontrol=dolu(1))
test("Analiz: gostergeler", PROD, "/api/stocks/{}/indicators".format(S), kontrol=dolu(alan="adx"))
test("Analiz: pivot seviyeleri", PROD, "/api/stocks/{}/pivot-levels".format(S), kontrol=dolu(alan="pivot"))
test("Analiz: pivot (2. hisse)", PROD, "/api/stocks/ASELS/pivot-levels", kontrol=dolu(alan="previous_close"))
test("Analiz: sektor kiyasi", PROD, "/api/stocks/{}/sector-comparison".format(S), kontrol=dolu(alan="sector_median_pe"))
test("Analiz: sinyal taramasi", PROD, "/api/signals", kontrol=dolu(1))
test("Analiz: tarayici", PROD, "/api/screener", kontrol=dolu(1))
test("Analiz: sektorler", PROD, "/api/sectors", kontrol=dolu(1))
test("Piyasa: seans durumu", PROD, "/api/market/status", kontrol=dolu(alan="is_open"))
test("Piyasa: kur/altin", PROD, "/api/market/quotes", kontrol=dolu(3, "price"))
test("Backtest: strateji listesi", PROD, "/api/backtest/strategies", kontrol=dolu(1))
test("Backtest: DCA", PROD, "/api/stocks/{}/dca-backtest".format(S), "POST",
     govde={"monthly_amount": 1000, "years": 3})
test("Backtest: RSI stratejisi", LOCAL, "/api/stocks/{}/backtest?strategy=RSI".format(S), token=TOKEN)
test("Backtest: SMA_CROSS", LOCAL, "/api/stocks/{}/backtest?strategy=SMA_CROSS".format(S), token=TOKEN)
test("Backtest: MACD", LOCAL, "/api/stocks/{}/backtest?strategy=MACD".format(S), token=TOKEN)

# ---------- 3. HABER VE KURUMSAL VERI ----------
test("Haber: KAP akisi", PROD, "/api/kap/news", kontrol=dolu(1))
test("Haber: onemli pay sahibi", PROD, "/api/kap/major-holder-news", kontrol=dolu(1))
test("Haber: hisse KAP bildirimleri", PROD, "/api/stocks/{}/kap-disclosures".format(S), kontrol=dolu(1))
test("Haber: hisse haberleri", PROD, "/api/stocks/{}/news".format(S), kontrol=dolu(1))
test("Kurumsal: iceriden ogrenen", PROD, "/api/stocks/{}/insider-trades".format(S), kontrol=dolu(1))
test("Kurumsal: yabanci takas trendi", PROD, "/api/stocks/{}/foreign-holding-trend".format(S), kontrol=dolu(1))
test("Kurumsal: temettu gecmisi", PROD, "/api/stocks/{}/dividend-history".format(S), kontrol=dolu(1))
test("Takvim: bilanco takvimi", PROD, "/api/earnings-calendar", kontrol=dolu(1))
test("Takvim: halka arzlar", PROD, "/api/ipos", kontrol=dolu(1, "company_name"))
test("Fonlar: liste", PROD, "/api/funds", kontrol=dolu(10))
test("Haber: piyasa akisi", PROD, "/api/market/news", kontrol=dolu(10, "title"))
test("Haber: kaynak listesi", PROD, "/api/market/news/sources", kontrol=dolu(5))
test("Haber: kaynak filtresi", PROD, "/api/market/news?source=Foreks", kontrol=dolu(1))
test("Haber: akis aramasi", PROD, "/api/market/news?q=borsa", kontrol=dolu(1))

# ---------- 4. PORTFOY VE ISLEM ----------
test("Portfoy: bos portfoy okunuyor", LOCAL, "/api/portfolio", token=TOKEN)
kod, g, _ = cagir(LOCAL, "/api/trade", "POST", {"symbol": S, "action_type": "AL", "quantity": 10}, token=TOKEN)
kapali = kod == 400 and "kapal" in str(g)
kaydet("TAMAM" if kod == 200 or kapali else "HATA", "Islem: AL emri",
       "seans kapali, dogru sekilde reddedildi" if kapali else "HTTP {} {}".format(kod, str(g)[:140]))
bekle("Islem: 0 adet reddi", (400, 422), LOCAL, "/api/trade", "POST",
      govde={"symbol": S, "action_type": "AL", "quantity": 0}, token=TOKEN)
bekle("Islem: negatif adet reddi", (400, 422), LOCAL, "/api/trade", "POST",
      govde={"symbol": S, "action_type": "AL", "quantity": -5}, token=TOKEN)
bekle("Islem: bakiye ustu reddi", (400, 422), LOCAL, "/api/trade", "POST",
      govde={"symbol": S, "action_type": "AL", "quantity": 99999999}, token=TOKEN)
bekle("Islem: elde yokken SAT reddi", (400, 422), LOCAL, "/api/trade", "POST",
      govde={"symbol": S, "action_type": "SAT", "quantity": 99999}, token=TOKEN)
bekle("Islem: olmayan hisse reddi", (400, 404, 422), LOCAL, "/api/trade", "POST",
      govde={"symbol": "YOKBOYLE", "action_type": "AL", "quantity": 1}, token=TOKEN)
test("Portfoy: dolu portfoy", LOCAL, "/api/portfolio", token=TOKEN)
test("Portfoy: analitik", LOCAL, "/api/portfolio/analytics", token=TOKEN)
test("Portfoy: risk paneli", LOCAL, "/api/portfolio/risk", token=TOKEN)
test("Portfoy: performans", LOCAL, "/api/portfolio/performance", token=TOKEN)
test("Portfoy: XU100 kiyasi", LOCAL, "/api/portfolio/benchmark", token=TOKEN)
test("Portfoy: performans karnesi", LOCAL, "/api/portfolio/scorecard", token=TOKEN)
test("Portfoy: temettu projeksiyonu", LOCAL, "/api/portfolio/dividends", token=TOKEN)
test("Portfoy: islem gecmisi", LOCAL, "/api/portfolio/transactions", token=TOKEN, kontrol=dolu(1))
bekle("Portfoy: CSV disa aktarim", (200,), LOCAL, "/api/portfolio/transactions/export", token=TOKEN)
kod, g, _ = cagir(LOCAL, "/api/trade", "POST", {"symbol": S, "action_type": "SAT", "quantity": 10}, token=TOKEN)
kapali = kod == 400 and "kapal" in str(g)
kaydet("TAMAM" if kod == 200 or kapali else "HATA", "Islem: SAT emri",
       "seans kapali, dogru sekilde reddedildi" if kapali else "HTTP {} {}".format(kod, str(g)[:140]))
test("Liderlik tablosu", LOCAL, "/api/leaderboard", kontrol=dolu(1))
bekle("Bakiye: sifirla", (200,), LOCAL, "/api/user/balance", "POST", govde={"new_balance": 100000}, token=TOKEN)

# ---------- 5. BEKLEYEN EMIRLER ----------
kod, g, _ = cagir(LOCAL, "/api/orders", "POST",
                  {"symbol": S, "order_type": "LIMIT_BUY", "quantity": 5, "target_price": 1.0}, token=TOKEN)
EMIR = (g or {}).get("id") if kod in (200, 201) else None
kaydet("TAMAM" if EMIR else "HATA", "Emir: olustur", "HTTP {} {}".format(kod, str(g)[:140]))
test("Emir: listele", LOCAL, "/api/orders", token=TOKEN, kontrol=dolu(1))
if EMIR:
    bekle("Emir: guncelle", (200,), LOCAL, "/api/orders/{}".format(EMIR), "PUT",
          govde={"quantity": 7, "target_price": 2.0}, token=TOKEN)
    bekle("Emir: sil", (200, 204), LOCAL, "/api/orders/{}".format(EMIR), "DELETE", token=TOKEN)
bekle("Emir: baskasinin emrini silme reddi", (400, 403, 404), LOCAL, "/api/orders/999999", "DELETE", token=TOKEN)

# ---------- 6. BOT ----------
test("Bot: durum", LOCAL, "/api/user/bot", token=TOKEN)
test("Bot: loglar", LOCAL, "/api/user/bot/logs", token=TOKEN)
test("Bot: oturumlar", LOCAL, "/api/user/bot/sessions", token=TOKEN)
test("Bot: performans", LOCAL, "/api/user/bot/performance", token=TOKEN)
bekle("Bot: ayar kaydet", (200,), LOCAL, "/api/user/bot/settings", "POST",
      govde={"is_active": True, "strategy": "RSI", "risk_mode": "normal"}, token=TOKEN)
bekle("Bot: bakiye ayarla", (200,), LOCAL, "/api/user/bot/balance", "POST",
      govde={"new_balance": 50000}, token=TOKEN)

# ---------- 7. IZLEME LISTESI ----------
bekle("Favori: ekle", (200, 201), LOCAL, "/api/watchlist/{}".format(S), "POST", govde={}, token=TOKEN)
test("Favori: listele", LOCAL, "/api/watchlist", token=TOKEN, kontrol=dolu(1))
bekle("Favori: sil", (200, 204), LOCAL, "/api/watchlist/{}".format(S), "DELETE", token=TOKEN)

# ---------- 8. TOPLULUK ----------
bekle("Topluluk: yorum yaz", (200, 201), LOCAL, "/api/stocks/{}/comments".format(S), "POST",
      govde={"comment_text": "Bu hisse iyi gorunuyor."}, token=TOKEN)
test("Topluluk: yorumlari oku", LOCAL, "/api/stocks/{}/comments".format(S), kontrol=dolu(1))
bekle("Topluluk: oy ver", (200, 201), LOCAL, "/api/stocks/{}/vote".format(S), "POST",
      govde={"direction": "UP"}, token=TOKEN)
test("Topluluk: duyarlilik skoru", LOCAL, "/api/stocks/{}/sentiment".format(S))

# ---------- 9. BILDIRIM ----------
test("Bildirim: liste", LOCAL, "/api/notifications", token=TOKEN)
test("Bildirim: okunmamis sayisi", LOCAL, "/api/notifications/unread-count", token=TOKEN)
bekle("Bildirim: hepsini okundu isaretle", (200,), LOCAL, "/api/notifications/read-all", "POST",
      govde={}, token=TOKEN)
bekle("Bildirim: fiyat alarmi kur", (200, 201), LOCAL, "/api/stocks/{}/notification-preference".format(S), "POST",
      govde={"target_price": 500, "direction": "USTUNDE"}, token=TOKEN)
test("Bildirim: alarmi oku", LOCAL, "/api/stocks/{}/notification-preference".format(S), token=TOKEN)
test("Push: abonelik durumu", LOCAL, "/api/push/status", token=TOKEN)

# ---------- 10. SINIR VE GUVENLIK ----------
bekle("Sinir: olmayan hisse 404", (404,), PROD, "/api/stocks/YOKBOYLEHISSE")
bekle("Sinir: gecersiz grafik araligi", (200, 400, 422), PROD, "/api/stocks/THYAO/history?range=SACMA")
bekle("Guvenlik: portfoy tokensiz reddi", (401, 403), LOCAL, "/api/portfolio")
bekle("Guvenlik: bozuk token reddi", (401, 403), LOCAL, "/api/portfolio", token="sahte.token.degeri")
bekle("Guvenlik: SQL enjeksiyon denemesi", (200, 400, 422), PROD,
      "/api/stocks/search?q=%27%20OR%201%3D1--")
bekle("Guvenlik: baskasinin portfoyu (id gezinme)", (401, 403, 404, 422), LOCAL, "/api/portfolio?user_id=1")

# ---------- RAPOR ----------
print()
simge = {"TAMAM": "[+]", "HATA": "[X]", "BOS": "[!]", "UYARI": "[~]"}
for durum, ad, mesaj, sure in sonuclar:
    sure_s = "{:5.2f}s".format(sure) if sure else "      "
    print("{} {:44} {} {}".format(simge.get(durum, "?"), ad, sure_s, mesaj))
print()
c = Counter(d for d, *_ in sonuclar)
print("TOPLAM {} test | tamam {} | HATA {} | BOS {} | uyari {}".format(
    len(sonuclar), c["TAMAM"], c["HATA"], c["BOS"], c["UYARI"]))
if CI:
    print("(CI modu: tum testler {} adresine kosuldu, 'BOS' bulgulari "
          "basarisizlik sayilmaz)".format(LOCAL))

# CIKIS KODU: yalnizca HATA basarisizliktir. BOS bir veri boru hatti sorunudur,
# sozlesme ihlali degil; CI'i kirmasi yanlis alarm uretir.
sys.exit(1 if c["HATA"] else 0)
