# BIST Sanal Borsa Simülatörü — Proje Rehberi

> Bu dosya projenin **tek kaynağıdır**. Hem insan hem yapay zekâ için yazıldı.
> Yeni bir oturuma başlayan bir AI, kodu baştan taramak zorunda kalmadan buradan
> ne olduğunu, neyin neden öyle yapıldığını ve nereden devam edeceğini anlayabilmeli.
>
> **Bir şey değiştirdiğinde bu dosyayı da güncelle.** Bayat doküman, dokümansızlıktan
> kötüdür — daha önce `eyup.md` "otomatik deploy yok" yazdığı için tam tersi
> yapılmak üzereydi.

---

## 1. Uygulama ne yapıyor

**https://borsa-trader.duckdns.org**

Borsa İstanbul hisseleri için **gerçek para kullanılmayan** bir yatırım
simülatörü. Kullanıcı 100.000 TL sanal bakiyeyle başlar, gerçek fiyatlarla
alım-satım yapar ve ücretli terminallerde para karşılığı sunulan analiz
araçlarına ücretsiz erişir.

Ayırt edici tarafı: rakiplerde (Midas vb.) olmayan **katılım (faizsiz) taraması,
strateji backtest'i, Piotroski F-Skoru, performans karnesi ve içeriden öğrenen
takibi** burada var.

**Hedef kitle:** Türk bireysel yatırımcı; katılım hassasiyeti olan kullanıcılar
özellikle gözetiliyor.

### Bozulmaz kural — Katılım (faizsiz finans)

> Kodun, veritabanı modellerinin, arayüz metinlerinin ve AI prompt'larının
> **hiçbir yerinde** "faiz", "interest", "mevduat" kelimesi veya mantığı
> kullanılmamalıdır. Tüm hesaplamalar reel ticaret, kâr payı, temettü ve
> değer artışı esasına dayanır.

Bu proje boyunca geçerli, istisnasız bir kısıttır.

---

## 2. Teknoloji ve altyapı

| Katman | Ne kullanılıyor |
|---|---|
| Backend | FastAPI + SQLAlchemy 2.x + Pydantic v2 (Python) |
| Frontend | Next.js 16 (App Router, Turbopack) + TailwindCSS + lucide-react |
| Grafik | lightweight-charts |
| Veritabanı | PostgreSQL 16 (`bist_app`) üretimde, SQLite yerelde |
| Zamanlayıcı | APScheduler (backend süreci içinde) |
| Kimlik | JWT HS256 |
| Sunucu | DigitalOcean VPS `209.38.208.160`, Frankfurt |
| Süreç yönetimi | pm2 (`borsa-backend`, `borsa-frontend`) |
| Ters vekil | nginx (aaPanel), Let's Encrypt otomatik yenileme |
| Deploy | GitHub Actions, `master`'a push'ta **otomatik** |

**Render, Vercel veya Heroku ile hiçbir bağlantı yoktur.** Proje bir dönem
Render'da barındırılması planlandığı için kodda o ortamı anlatan yorumlar
kalmıştı; 2026-08-27'de temizlendi.

### Henüz kullanılmayanlar

Redis yok, WebSocket yok, Docker yok, kalıcı test paketi yok (yalnızca
`backend/test_bot.py`), hata izleme (Sentry vb.) yok. Bunlar bilinçli
eksikler — ölçek henüz gerektirmedi. Sinyal önbelleği süreç içi bir sözlük
olduğu için **backend tek işçiyle çalışmalıdır**; çok işçili yapıya geçilecekse
önce önbellek Redis'e taşınmalıdır.

---

## 3. Dizin yapısı

```
backend/           FastAPI uygulaması
  main.py            79 API ucu — uygulamanın merkezi
  models.py          30 SQLAlchemy modeli
  schemas.py         Pydantic şemaları
  scheduler.py       7 zamanlanmış iş
  init_db.py         Tablo oluşturma + migration + hisse kataloğu tohumu
frontend/src/app/  Next.js App Router — 14 sayfa, 37 bileşen
ops/               Sunucu işletim betikleri (yedekleme)
.github/workflows/ deploy.yml, backup.yml
```

### Backend modülleri ne işe yarar

| Dosya | Sorumluluk |
|---|---|
| `analysis_engine.py` | Derin şirket analizi, analist konsensüsü |
| `financials.py` | Bilanço/gelir tablosu çekme ve normalleştirme |
| `katilim.py` | Katılım (faizsiz) uygunluk oranları |
| `indicators.py` | Stochastic, ADX, OBV |
| `signals.py` | Teknik sinyal taraması (kesişim vb.) |
| `backtest.py` | Strateji geriye dönük testi |
| `scorecard.py` | Performans karnesi (FIFO tutma süresi) |
| `bot.py` | Kişisel kural tabanlı işlem botu |
| `orders.py` | Bekleyen limit emirleri |
| `transactions.py` | AL/SAT işlemleri |
| `tr_market.py` | Döviz / gram altın (yurt içi kaynak) |
| `daily_history.py` | Günlük OHLCV + endeks geçmişi |
| `yfinance_client.py` | Toplu fiyat çekme |
| `yf_retry.py` | yfinance yeniden deneme + proxy |
| `kap_client.py` | KAP bildirimleri |
| `insider_client.py` | İçeriden öğrenen işlemleri |
| `tefas_client.py` | TEFAS yatırım fonları |
| `sentiment.py` | Sözlük tabanlı duyarlılık skoru |
| `notifications.py` | Bildirim üretimi (outbox deseni) |
| `push.py` | Web Push gönderimi (VAPID) |
| `cache.py` | Basit süreç içi önbellek |
| `market_hours.py` | Borsa açık mı kontrolü |

---

## 4. Özellikler

**Portföy ve işlem** — Sanal bakiye, AL/SAT, bekleyen limit emirleri, işlem
geçmişi + CSV dışa aktarım, portföy analitiği, risk paneli, XU100'e karşı kıyas,
performans grafiği, performans karnesi (isabet oranı + FIFO tutma süresi),
temettü geliri projeksiyonu, liderlik tablosu.

**Analiz** — Derin bilanço analizi, finansal tablolar, Piotroski F-Skoru, analist
konsensüsü (hedef fiyat, al/tut/sat), RSI/MACD/SMA/Stochastic/ADX/OBV, pivot
seviyeleri, sinyal taraması, strateji backtest'i (RSI/SMA_CROSS/MACD), DCA
backtest, hisse ve sektör karşılaştırma, katılım taraması, ısı haritası, tarayıcı.

**Veri ve haber** — KAP bildirimleri, önemli pay sahibi haberleri, hisse
haberleri, içeriden öğrenen işlemleri, yabancı takas oranı trendi, bilanço
takvimi, halka arzlar, TEFAS fonları, döviz/altın/BIST 100.

**Diğer** — Kişisel bot (strateji + risk modu, oturum, log, performans),
topluluk yorumları + duyarlılık + oylama, web push bildirimleri (fiyat, KAP,
sinyal alarmları), PWA (iOS dahil), gecelik yedekleme.

### "AI" etiketi hakkında — önemli

Projede **gerçek bir yapay zekâ / LLM entegrasyonu yoktur.** "AI Trader",
"AI sinyali" diye geçen her şey kural tabanlıdır:

- **Sinyaller** → gösterge eşikleri (RSI < 30 gibi)
- **Duyarlılık** → 22 pozitif + 19 negatif kelimelik sözlük (`sentiment.py`);
  olumsuzlamayı anlamaz, "bu hisse düşmez" cümlesini negatif sayar
- **Bot** → if/else strateji

Kural tabanlı olmak kusur değil (öngörülebilir ve denetlenebilir), ama
**etiket gerçeği karşılamıyor.** Ya etiket düzeltilmeli ya gerçek LLM eklenmeli.

---

## 5. Veri kaynakları

| Veri | Kaynak | Tazeleme |
|---|---|---|
| Hisse fiyatları | yfinance (proxy üzerinden) | Hafta içi 10–18, 5 dakika |
| Günlük OHLCV | yfinance | Günlük 08:00 UTC |
| Bilanço / analiz | yfinance | Günlük 02:00 UTC, en bayat 40 hisse |
| KAP bildirimleri | kap.org.tr | Günlük 08:00 UTC |
| Fonlar | tefas.gov.tr | Günlük 08:00 UTC |
| Haberler | yfinance | Günlük 07:30 UTC |
| **Dolar / Euro / Gram altın** | **finans.truncgil.com** (yedek: TCMB) | **15 dakika, 7/24** |
| BIST 100 endeksi | yfinance | Seans içinde 15 dakika |

### yfinance neden proxy üzerinden

Veri merkezi IP'leri (bizimki DigitalOcean Frankfurt) çok sayıda yfinance
kullanıcısı tarafından paylaşıldığı için Yahoo Finance tarafında **kalıcı olarak
engellendi** — basit hız sınırından farklı, kendiliğinden açılmıyor. Çözüm
`YF_PROXY_URL` ortam değişkeni (bkz. `yf_retry.py`). Bu olmadan üretimde
hisse fiyatı hiç gelmez.

Truncgil ve TCMB **proxy gerektirmez**, doğrudan erişilir.

### Gram altın neden türetilmiyor

yfinance'ta gram altın sembolü yok. Eskiden ons altın × dolar kuru ile
türetiliyordu ve ons için `GC=F` kullanılıyordu — ama `GC=F` COMEX **vadeli**
sözleşmesidir, spot değil, ve spotun üstünde işlem görür. Ölçüldü: `GC=F`
4695,60 USD iken spot ons 4641,83 USD, yani %1,16 fark; gram altına yansıması
7175,52 TL yerine 7251,81 TL. Bu gürültü değil, **sistematik sapmaydı.**

Artık gram altın yurt içi kaynaktan hazır alınıyor. Kaynağın gram altını, kendi
ons ve dolar değerlerinin paritesine kuruşu kuruşuna eşit — yani kara kutu değil,
iç tutarlılığı doğrulandı.

Eski dönemin `GRAMALTIN` satırları veritabanında `source='yfinance-gcf'` olarak
etiketli ve uçtan **dışlanıyor**; yeni spot verisiyle karıştırılırsa 30 günlük
değişim gerçekte olmayan bir sıçrama gösterirdi.

### Zamanlanmış işler (`scheduler.py`)

| İş | Ne zaman |
|---|---|
| `bist_updater` | Hafta içi 10–18, her 5 dakika |
| `tr_quotes_sync` | Her 15 dakika, 7/24 |
| `deep_analysis_sync` | Her gün 02:00 UTC |
| `stock_news_sync` | Her gün 07:30 UTC |
| `market_data_sync` | Her gün 08:00 UTC |
| `user_portfolio_snapshot` | Hafta içi 15:30 UTC |
| `log_cleaner` | Pazar 03:00 UTC |

---

## 6. Tasarım sistemi ("Anti-AI Blue")

Jenerik elektrik mavisi, mor parlama ve neon efektler yerine **obsidyen siyahı +
sıcak kehribar** paleti.

| Eleman | Kod |
|---|---|
| Arka plan | `#0B0E14` |
| Kart / yüzey | `#151921` |
| Sınır | `#242B35` |
| Yükseliş | `#10B981` |
| Düşüş | `#F43F5E` |
| Vurgu | `#F59E0B` |
| Birincil metin | `#F8FAFC` |
| İkincil metin | `#8A99AD` |

**Kurallar**

- Finansal sayılarda `tabular-nums` **zorunlu** — canlı güncellenirken kaymasın.
- **Yasak ikonlar:** sihirli değnek, ışıltı, robot, beyin. Ağır glassmorphism de yasak.
- İzin verilen: yalnızca lucide-react, 1.5px ince çizgi.
- Dokunma hedefi en az **44×44px**.
- Geniş tablolar `overflow-x-auto` ile kendi içinde kayar; sayfa gövdesi yatay kaymaz.
- Mobilde sabit alt gezinme barı (`md:hidden`).

---

## 7. Geliştirme ve deploy

### Yerel çalıştırma

```bash
# Backend  (http://localhost:4000)
cd backend && ./venv/Scripts/python.exe -m uvicorn main:app --reload --port 4000

# Frontend (http://localhost:3000)
cd frontend && npm run dev
```

Yerelde `DATABASE_URL` tanımlı değilse SQLite'a düşer. **Üretimde SQLite
kullanılmamalıdır** — eşzamanlı yazmada kilitlenir, scheduler ile API aynı anda yazar.

### Deploy — otomatik

`master`'a push at, bitti. `.github/workflows/deploy.yml` sunucuya bağlanır,
kodu çeker, frontend'i derler, pm2'yi yeniden başlatır.

```bash
git push            # deploy başlar
gh run watch        # izle
```

**Atomik `.next` takası:** frontend `.next-build` dizinine derlenir, ancak
başarılı olursa `mv` ile yerine geçer. Derleme patlarsa **canlı site eski
haliyle ayakta kalır.** Bu, bu projede iki kez üretimi kurtardı — kaldırma.

Elle müdahale gerekirse (deploy patlarsa):

```bash
ssh root@209.38.208.160
cd /opt/borsa && git pull origin master
cd backend  && ./venv/bin/pip install -r requirements.txt && pm2 restart borsa-backend
cd frontend && npm install && npm run build && pm2 restart borsa-frontend
pm2 status && pm2 logs borsa-backend --lines 30
```

### Veritabanı şeması değişikliği

`create_all()` yalnızca **eksik TABLOLARI** oluşturur, var olan tabloya
**kolon EKLEMEZ.** Yeni kolon eklerken `init_db.py` içindeki `MIGRATIONS`
sözlüğüne de yazılmalıdır, yoksa üretimde kolon hiç oluşmaz.

> `MIGRATIONS` içinde aynı tablo adını **iki kez** anahtar olarak yazma —
> Python yinelenen anahtarı sessizce ezer ve migration hiç çalışmaz.

### Ortam değişkenleri (`/opt/borsa/backend/.env`)

`DATABASE_URL`, `JWT_SECRET_KEY`, `FRONTEND_URL`, `YF_PROXY_URL`,
`ENVIRONMENT=production`, `VAPID_*` (web push).

---

## 8. Yedekleme ve geri yükleme

İki katmanlı. Sunucudaki yedek "yanlışlıkla sildim"i kurtarır, sunucu dışındaki
"VPS gitti"yi.

### Katman 1 — Sunucu içi (çalışıyor)

| | |
|---|---|
| Betik | `ops/backup-db.sh` → sunucuda `/usr/local/bin/bist-backup.sh` |
| Zamanlama | Her gün 03:30 UTC, root crontab |
| Konum | `/var/backups/bist/daily/`, `/var/backups/bist/weekly/` |
| Saklama | 14 günlük + 8 haftalık |
| Günlük | `/var/log/bist-backup.log` |

Betik dökümü `pg_restore --list` ile **doğrular**; nesne sayısı 10'un altındaysa
hata verir. Yazarken `.partial` uzantısı kullanır, yarım dosya asla geçerli
yedek gibi görünmez.

Betik güncellenirse sunucuya yeniden kopyalanmalı — `scp` ile
`/usr/local/bin/bist-backup.sh` konumuna gönder, ardından sunucuda CRLF satır
sonlarını temizle (`sed -i 's/\r$//'`) ve `chmod +x` ver. Windows'tan kopyalanan
dosyada bu temizlik yapılmazsa bash betiği çalıştıramaz.

### Katman 2 — Sunucu dışı (ŞU AN ÇALIŞMIYOR)

`.github/workflows/backup.yml` her gün 04:00 UTC'de sunucudan taze döküm alır,
**runner'da** GPG/AES256 ile şifreler, 90 gün saklanan artifact olarak yükler.
Şifreleme runner'da yapılır ki parola sunucunun süreç listesine düşmesin.

**`BACKUP_PASSPHRASE` secret'ı tanımlı olmadığı için iş her sabah hata veriyor.**
Bu bilinçli: şifresiz döküm yüklemektense patlaması iyidir (döküm kullanıcı
e-postaları ve parola özetleri içerir).

```bash
gh secret set BACKUP_PASSPHRASE --body "PAROLA"
```

> GitHub secret'ları geri okunamaz. Parolayı mutlaka bir parola yöneticisinde sakla —
> kaybolursa sunucu dışı yedekler açılamaz hale gelir.

### Geri yükleme

```bash
LATEST=$(ls -1t /var/backups/bist/daily/*.dump | head -1)

# ÖNCE boş bir veritabanına yükleyip doğrula — canlıyı doğrudan ezme.
sudo -u postgres createdb bist_restore_test
sudo -u postgres pg_restore --no-owner --no-privileges -d bist_restore_test "$LATEST"
sudo -u postgres psql -tAc "SELECT count(*) FROM users" bist_restore_test
```

Sayılar beklendiği gibiyse:

```bash
pm2 stop borsa-backend
sudo -u postgres dropdb bist_app && sudo -u postgres createdb bist_app
sudo -u postgres pg_restore --no-owner --no-privileges -d bist_app "$LATEST"
pm2 start borsa-backend
```

Şifreli yedekten: GitHub → Actions → "Database Backup (off-site)" → artifact indir,
sonra `gpg --batch --decrypt --passphrase 'PAROLA' --output bist_app.dump <dosya>.gpg`
ile çöz ve yukarıdaki `pg_restore` adımını uygula.

**Prova kaydı** — test edilmemiş yedek yedek sayılmaz.

| Tarih | Sonuç |
|---|---|
| 2026-08-23 | Geçici veritabanına geri yüklendi. `users`, `portfolios`, `transactions`, `stock_prices_daily` (45.113 satır), `financial_statements`, `watchlist`, `notifications` — hepsi kaynakla birebir eşit. |

---

## 9. Bu koda dokunmadan önce bilmen gerekenler

Hepsi gerçek hatalardan öğrenildi. Tekrarlanmaması için buradalar.

**Fan-out tuzağı.** `Stock` ile 1:N ilişkideki bir tabloyu `outerjoin` edip
`.limit(N)` uygulamak, birleşmiş satırları sınırlar; tekilleştirme sonrası
elinde N'den **çok daha az** varlık kalır. `financials.py` bu yüzden aylarca
istediğinin beşte birini işledi ve bilanço kapsamı 39 hissede takılı kaldı.
Çözüm: önce alt sorguyla hisse başına tek satıra indirge, sonra join et.

**`ROW_NUMBER() OVER (PARTITION BY ...)` bölümün tamamını okur.** Zaman filtresi
konmazsa maliyet veri büyüdükçe doğrusal artar. En son tik sorgusu 208 satır
için 57.436 satır tarıyordu.

**Önbellek yazımı ile okuması ayrı şeylerdir.** `use_cache=False` bayrağı hem
okumayı hem yazmayı kapatıyordu; scheduler'ın önbellek ısıtma çağrısı bu yüzden
hiçbir şey doldurmayacaktı.

**`is_market_open()` demet döndürür** → `(açık_mı, sebep)`. `if is_market_open():`
yazmak her zaman doğru verir, çünkü boş olmayan demet doğrudur.

**Türkçe sayı ayrıştırma sessizce bozar.** `float("7.175")` patlamaz, **7,175**
döndürür — bin kat küçük. Nokta binlik ayracıdır, elle ayrıştır (`tr_market.tr_sayi`).

**Zaman damgasına "Z" eklemeyi unutma.** Backend UTC üretir ama saat dilimi eki
koymaz; JavaScript eki olmayan metni **yerel saat** sayar ve sonuç 3 saat kayar.

**Service worker'da `event.waitUntil` / `await cache.put`'u `respondWith`
içinden çağırma.** `InvalidStateError` atıp yanıtı reddeder ve **dosya hiç
yüklenmez.** Önbellek süslemesi yüzünden sayfa bozulmaz.

**nginx `proxy_cache`** bu projede "eski arayüz görünüyor" sorununun kök
nedeniydi. Deploy sonrası bayat içerik gelirse ilk oraya bak.

**Heredoc ile Python betiği gönderirken Türkçe karakter kullanma.** stdin
kodlamasında bozulur, `str.replace` sessizce eşleşmez ve değişiklik hiç
uygulanmaz. **Her replace'e `assert` koy.**

**Test dosyalarını sunucudaki repoya kopyalama.** Deploy `git pull` yaptığında
"local changes would be overwritten" ile patlar. Geçici dosyalar `/tmp`'ye.

**Web Push TTL'i 0 bırakma.** Cihaz o an ulaşılamazsa bildirim sessizce düşer.

---

## 10. Bilinen eksikler ve sıradaki işler

### Doğruluk sorunları (öncelikli)

1. **Simülatörde komisyon yok.** `backtest.py` %0,02 komisyon uyguluyor ama
   gerçek AL/SAT işlemlerinde hiçbir maliyet kesilmiyor. Sonuç ters: kullanıcının
   kendi işlemleri backtest'ten sistematik olarak daha kârlı görünüyor.
2. **Katılım oranları yer tutucu.** `init_db.py`'deki `purification_rate`
   değerleri ikişerli tekrar eden yuvarlak sayılar — gerçek endeks verisi değil.
   Üretimde 111/165 hisse "BELİRSİZ". Rozet gösteriyoruz ama arkasında sağlam
   veri yok. Ya gerçek BIST Katılım Endeksi verisine bağlanmalı ya rozet
   kaldırılmalı.
3. **`BACKUP_PASSPHRASE` tanımlı değil** → sunucu dışı yedek yok (bkz. §8).

### Planlanan geliştirmeler

Eski `road_map.md`'deki 7 modülün **hepsi tamamlandı** (katılım rozeti, halka arz
takvimi, aracı kurum konsensüsü, ısı haritası, bilanço/KAP takvimi, topluluk
duygu durumu, bildirim sistemi). Yazılı planda bekleyen iş kalmadı.

Konuşulan ama henüz başlanmayanlar:

| Öncelik | İş | Neden |
|---|---|---|
| 1 | pytest + CI | Kalıcı test yok; her değişiklikte tek kullanımlık betik yazılıyor |
| 2 | Redis önbellek | Süreç içi önbellek çok işçili yapıyı engelliyor |
| 3 | KAP bildirimi LLM özeti | Veri hazır (498 bildirim), kimse ücretsiz sunmuyor |
| 4 | Doğal dille tarayıcı | LLM sadece filtre üretir, sayı üretmez → halüsinasyon riski yapısal olarak yok |
| 5 | Bilanço LLM yorumu | Veri hazır (157 hisse) |
| 6 | WebSocket canlı fiyat | Şu an poll ediliyor |
| 7 | Sentry | Kullanıcı hatası pm2 logunda kalıyor, kimse görmüyor |

**LLM eklenirse ilke:** model **sayı üretmesin**, bizim ürettiğimiz sayıyı
açıklasın veya sorguya çevirsin. Fiyat tahmini yaptırma — hem göstergelerden
iyi değil hem sorumluluk riski.

Gerekmediği değerlendirilenler: Celery (APScheduler bu ölçekte yeterli),
Kubernetes (tek VPS için abartı).

### Kapsam

165 aktif hisse (BİST'te ~550 işlem görüyor) — kapsam artırılabilir.
Tek endeks izleniyor (XU100); XU030, XUBANK, katılım endeksi eklenebilir.

---

## 11. Veri durumu (2026-08-27)

| | |
|---|---|
| Aktif hisse | 165 |
| Bilançosu olan | 157 |
| Derin analizi olan | 165 |
| Temettü geçmişi olan | 128 |
| Günlük OHLCV | 165 hisse / 188.001 satır |
| Katılım oranı hesaplanmış | 137 |
| KAP bildirimi | 498 |
| Kullanıcı | 6 |

---

## 12. Yasal

Uygulama **yatırım tavsiyesi değildir** ve bunu arayüzde açıkça belirtir
(`LegalDisclaimerModal`, `Footer`). Gerçek para kullanılmaz. Veriler en az
15 dakika gecikmelidir. Alt bilgi imzası: *Design by Eyüphan İpek Hazretleri (ks)*.
