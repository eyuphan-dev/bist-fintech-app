"""
Pazaryeri (kullanici sepetleri) uctan uca testi. Gecici bir SQLite uzerinde
uygulamayi kendi icinde ayaga kaldirir (TestClient); calisan sunucu gerekmez.
Piyasa saati kilidi test icinde acilir. Yayin/kopyalama/silme yetkileri, agirlik
dogrulamasi, XSS temizligi ve puan kurallari kontrol edilir.

Calistir: python test_marketplace.py
"""
import os, sys, io, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
db_file = os.path.join(tempfile.gettempdir(), "mp_test.db")
if os.path.exists(db_file):
    os.remove(db_file)
os.environ["DATABASE_URL"] = "sqlite:///" + db_file.replace("\\", "/")
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["JWT_SECRET_KEY"] = "test-key"

from database import SessionLocal
import init_db, ci_seed
init_db.init_database()
ci_seed.seed(SessionLocal())

import main, models
from fastapi.testclient import TestClient

main.app.state.limiter.enabled = False
main.is_market_open = lambda force_open=False: (True, "test")
c = TestClient(main.app)

ok = fail = 0
def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1; print("OK  ", name)
    else:
        fail += 1; print("FAIL", name, extra)

def user(name):
    r = c.post("/api/auth/register", json={"username": name, "email": f"{name}@x.com", "password": "Sifre123!x", "terms_accepted": True})
    assert r.status_code == 201, r.text
    t = c.post("/api/auth/login", json={"username": name, "password": "Sifre123!x"}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}

A, B = user("alice"), user("bob")
db = SessionLocal()
syms = [s.symbol for s in db.query(models.Stock).all() if main._get_latest_db_price(db, s.id)][:3]
print("semboller", syms)

body = {"name": "Deneme Sepeti", "description": "test <script>alert(1)</script>",
        "items": [{"symbol": syms[0], "weight_pct": 60}, {"symbol": syms[1], "weight_pct": 40}]}

r = c.post("/api/marketplace", json=body)
check("auth zorunlu (publish)", r.status_code in (401, 403), r.status_code)
r = c.get("/api/marketplace")
check("auth zorunlu (liste)", r.status_code in (401, 403), r.status_code)

r = c.post("/api/marketplace", json=body, headers=A)
check("yayinla 200", r.status_code == 200, r.text)
basket = r.json()
check("XSS temizlendi", "<script" not in (basket["description"] or ""), basket["description"])
check("baslangic getirisi 0", basket["getiri_pct"] == 0.0, basket["getiri_pct"])
check("is_mine", basket["is_mine"] is True)
bid = basket["id"]

bad_sum = dict(body, items=[{"symbol": syms[0], "weight_pct": 50}, {"symbol": syms[1], "weight_pct": 40}])
check("agirlik toplami 100 degil -> 422", c.post("/api/marketplace", json=bad_sum, headers=A).status_code == 422)
dup = dict(body, items=[{"symbol": syms[0], "weight_pct": 50}, {"symbol": syms[0], "weight_pct": 50}])
check("ayni hisse iki kez -> 422", c.post("/api/marketplace", json=dup, headers=A).status_code == 422)
one = dict(body, items=[{"symbol": syms[0], "weight_pct": 100}])
check("tek hisse -> 422", c.post("/api/marketplace", json=one, headers=A).status_code == 422)
neg = dict(body, items=[{"symbol": syms[0], "weight_pct": 150}, {"symbol": syms[1], "weight_pct": -50}])
check("negatif agirlik -> 422", c.post("/api/marketplace", json=neg, headers=A).status_code == 422)
unk = dict(body, items=[{"symbol": "YOKBOYLE", "weight_pct": 50}, {"symbol": syms[1], "weight_pct": 50}])
check("bilinmeyen hisse -> 400", c.post("/api/marketplace", json=unk, headers=A).status_code == 400)
sqli = dict(body, items=[{"symbol": "A' OR 1=1--", "weight_pct": 50}, {"symbol": syms[1], "weight_pct": 50}])
check("sembolde SQLi karakteri -> 422", c.post("/api/marketplace", json=sqli, headers=A).status_code == 422)

# listeleme + kopyalama
r = c.get("/api/marketplace?sort=getiri", headers=B)
check("liste 1 sepet", r.status_code == 200 and len(r.json()) == 1, r.text)
check("baskasinin sepeti is_mine=False", r.json()[0]["is_mine"] is False)
check("gecersiz sort -> 422", c.get("/api/marketplace?sort=x", headers=B).status_code == 422)

bal0 = c.get("/api/auth/me", headers=B).json()["virtual_balance"]
r = c.post(f"/api/marketplace/{bid}/copy", json={"amount": 10000}, headers=B)
check("kopyala 200", r.status_code == 200, r.text)
if r.status_code == 200:
    d = r.json()
    check("2 hisse alindi", len(d["alinanlar"]) == 2, d)
    check("harcanan ~10000", abs(d["toplam_harcanan"] - 10000) < 1, d["toplam_harcanan"])
    bal1 = c.get("/api/auth/me", headers=B).json()["virtual_balance"]
    check("bakiye dustu", abs((bal0 - bal1) - d["toplam_harcanan"]) < 0.02, (bal0, bal1))
pts = c.get("/api/auth/me", headers=A).json()["game_points"]
check("yayinci +5 puan", pts == 5, pts)
c.post(f"/api/marketplace/{bid}/copy", json={"amount": 1000}, headers=B)
pts = c.get("/api/auth/me", headers=A).json()["game_points"]
check("ayni kisi tekrar kopyalayinca puan artmaz", pts == 5, pts)
r = c.post(f"/api/marketplace/{bid}/copy", json={"amount": 500}, headers=A)
check("yayinci kendi sepetini kopyalar (puan yok)", r.status_code == 200, r.text)
check("kendi kopyasi puan vermez", c.get("/api/auth/me", headers=A).json()["game_points"] == 5)
r = c.get(f"/api/marketplace/{bid}", headers=A)
check("kopya_sayisi = 1 (yayinci sayilmaz)", r.json()["kopya_sayisi"] == 1, r.json()["kopya_sayisi"])

check("yetersiz bakiye -> 400", c.post(f"/api/marketplace/{bid}/copy", json={"amount": 9_000_000}, headers=B).status_code == 400)
check("negatif tutar -> 422", c.post(f"/api/marketplace/{bid}/copy", json={"amount": -5}, headers=B).status_code == 422)
check("olmayan sepet -> 404", c.post("/api/marketplace/99999/copy", json={"amount": 100}, headers=B).status_code == 404)

# silme yetkisi (IDOR)
check("baskasi silemez -> 404", c.delete(f"/api/marketplace/{bid}", headers=B).status_code == 404)
check("hala listede", len(c.get("/api/marketplace", headers=B).json()) == 1)
check("sahibi siler", c.delete(f"/api/marketplace/{bid}", headers=A).status_code == 200)
check("silinen listede yok", len(c.get("/api/marketplace", headers=B).json()) == 0)
check("silinen kopyalanamaz -> 404", c.post(f"/api/marketplace/{bid}/copy", json={"amount": 100}, headers=B).status_code == 404)

# aktif sepet limiti
for i in range(5):
    c.post("/api/marketplace", json=dict(body, name=f"Sepet {i}"), headers=A)
check("6. sepet -> 400", c.post("/api/marketplace", json=dict(body, name="Fazla"), headers=A).status_code == 400)

# mevcut tematik sepet yatirimi bozulmadi (refactor edilen yol)
for st in db.query(models.Stock).filter(models.Stock.symbol.in_(syms)).all():
    db.add(models.CompanyAnalysis(stock_id=st.id, market_cap=1e10))
db.commit()
r = c.post("/api/baskets/buyuk-sermaye/invest", json={"amount": 5000}, headers=B)
check("tematik sepet yatirimi hala calisiyor", r.status_code == 200, r.text)

print(f"\n{ok} basarili, {fail} basarisiz")
sys.exit(1 if fail else 0)
