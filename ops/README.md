# Sunucu İşletim Notları

## Veritabanı yedekleme

Yedekleme iki katmanlı: biri sunucuda, biri sunucu dışında. İkisi de gerekli —
sunucudaki yedek "yanlışlıkla sildim"i kurtarır, sunucu dışındaki "VPS gitti"yi.

### Katman 1 — Sunucu içi (gecelik)

| | |
|---|---|
| Betik | `ops/backup-db.sh` → sunucuda `/usr/local/bin/bist-backup.sh` |
| Zamanlama | Her gün 03:30 UTC (06:30 TR), root crontab |
| Konum | `/var/backups/bist/daily/` ve `/var/backups/bist/weekly/` |
| Saklama | 14 günlük + 8 haftalık (pazar günleri haftalığa kopyalanır) |
| Günlük | `/var/log/bist-backup.log` |

Betik dökümü aldıktan sonra `pg_restore --list` ile **doğrular**; nesne sayısı
10'un altındaysa dosyayı geçerli yedeklerin arasına koymadan hata verir.
Yazma sırasında `.partial` uzantısı kullanılır, böylece yarım kalmış bir dosya
asla geçerli yedek gibi görünmez.

Betik güncellenirse sunucuya yeniden kopyalanmalı:

```bash
scp ops/backup-db.sh root@SUNUCU:/usr/local/bin/bist-backup.sh
ssh root@SUNUCU 'sed -i "s/\r$//" /usr/local/bin/bist-backup.sh && chmod +x /usr/local/bin/bist-backup.sh'
```

(`sed` satırı Windows'tan kopyalanan dosyadaki CRLF satır sonlarını temizler —
onsuz `bash` betiği çalıştıramaz.)

### Katman 2 — Sunucu dışı (GitHub Actions)

`.github/workflows/backup.yml` her gün 04:00 UTC'de çalışır: sunucuda taze bir
döküm aldırır, indirir, **runner'da** GPG/AES256 ile şifreler ve 90 gün
saklanan bir artifact olarak yükler. Döküm kullanıcı e-postaları ve parola
özetleri içerdiği için şifresiz saklanmaz.

**Gerekli secret:** `BACKUP_PASSPHRASE`. Tanımlı değilse iş bilinçli olarak
hata verir (sessizce şifresiz yedek almaktansa patlaması iyidir).

> **UYARI:** GitHub secret'ları geri okunamaz, yalnızca üzerine yazılabilir.
> Bu parolayı mutlaka GitHub dışında bir yerde (parola yöneticisi) sakla.
> Parola kaybolursa sunucu dışı yedekler açılamaz hale gelir.

## Geri yükleme

### Sunucu içi yedekten

```bash
LATEST=$(ls -1t /var/backups/bist/daily/*.dump | head -1)

# ÖNCE boş bir veritabanına geri yükleyip doğrula — canlıyı doğrudan ezme.
sudo -u postgres createdb bist_restore_test
sudo -u postgres pg_restore --no-owner --no-privileges -d bist_restore_test "$LATEST"
sudo -u postgres psql -tAc "SELECT count(*) FROM users" bist_restore_test
```

Sayılar beklendiği gibiyse canlıya alma:

```bash
pm2 stop borsa-backend
sudo -u postgres dropdb bist_app && sudo -u postgres createdb bist_app
sudo -u postgres pg_restore --no-owner --no-privileges -d bist_app "$LATEST"
pm2 start borsa-backend
```

### Sunucu dışı (şifreli) yedekten

GitHub → Actions → "Database Backup (off-site)" → son çalıştırma → artifact indir.

```bash
gpg --batch --decrypt --passphrase 'PAROLA' \
    --output bist_app.dump bist_app-YYYYMMDD.dump.gpg
pg_restore --no-owner --no-privileges -d bist_app bist_app.dump
```

## Prova kaydı

Yedek geri yükleme **test edilmiştir**; test edilmemiş yedek yedek sayılmaz.

| Tarih | Sonuç |
|---|---|
| 2026-08-23 | Geçici veritabanına geri yüklendi. `users`, `portfolios`, `transactions`, `stock_prices_daily` (45.113 satır), `financial_statements`, `watchlist`, `notifications` — hepsi kaynakla **birebir eşit**. Geçici veritabanı silindi. |
