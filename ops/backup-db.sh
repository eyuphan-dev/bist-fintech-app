#!/usr/bin/env bash
#
# backup-db.sh — bist_app veritabaninin gecelik yedegi
#
# Cron'dan root olarak calisir (bkz. ops/README.md). Uc sey yapar:
#   1. pg_dump ile sikistirilmis "custom" formatta dokum alir
#   2. DOKUMU DOGRULAR - bozuk bir yedek, yedek degildir
#   3. Eskileri temizler (14 gunluk + 8 haftalik saklanir)
#
# Custom format (-Fc) tercih edildi: duz SQL'e gore hem kucuk, hem de
# pg_restore ile tek bir tabloyu geri almaya izin veriyor.
#
set -euo pipefail

DB_NAME="${DB_NAME:-bist_app}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/bist}"
DAILY_KEEP=14
WEEKLY_KEEP=8

DAILY_DIR="$BACKUP_DIR/daily"
WEEKLY_DIR="$BACKUP_DIR/weekly"
mkdir -p "$DAILY_DIR" "$WEEKLY_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
TARGET="$DAILY_DIR/${DB_NAME}-${STAMP}.dump"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "Yedek aliniyor: $DB_NAME -> $TARGET"

# Once gecici bir dosyaya yazilir. Yedek sirasinda surec olurse yarim bir
# dosya "gecerli yedek" gibi durmasin.
# NOT: --file yerine stdout kullaniliyor. --file ile dosyayi POSTGRES kullanicisi
# acmaya calisir ve /var/backups altina yazma izni olmadigi icin patlar;
# yonlendirme ise betigi calistiran root tarafindan yapilir.
TMP="$TARGET.partial"
sudo -u postgres pg_dump --format=custom --compress=9 "$DB_NAME" > "$TMP"

# DOGRULAMA: pg_restore -l dokumun icindekiler listesini okur. Dosya bozuksa
# veya yarim kaldiysa burada patlar ve dosya .partial olarak kalir, yani
# gecerli yedeklerin arasina karismaz.
OBJECTS="$(pg_restore --list "$TMP" | grep -c '^[0-9]' || true)"
if [ "$OBJECTS" -lt 10 ]; then
  log "HATA: dokum dogrulanamadi (yalnizca $OBJECTS nesne). Yedek atildi."
  exit 1
fi

mv "$TMP" "$TARGET"
SIZE="$(du -h "$TARGET" | cut -f1)"
log "Tamam: $SIZE, $OBJECTS nesne."

# Pazar gunleri ayni dosya haftaliga da kopyalanir. Boylece uzun sureli bir
# bozulma (ornegin 3 hafta once bozulmus ve fark edilmemis veri) icin de
# geri donulecek bir nokta kalir.
if [ "$(date +%u)" = "7" ]; then
  cp "$TARGET" "$WEEKLY_DIR/"
  log "Haftalik kopya alindi."
fi

# Rotasyon - en yeniler kalir.
prune() {
  local dir="$1" keep="$2"
  local n
  n="$(ls -1t "$dir"/*.dump 2>/dev/null | wc -l)"
  if [ "$n" -gt "$keep" ]; then
    ls -1t "$dir"/*.dump | tail -n +$((keep + 1)) | while read -r f; do
      log "Siliniyor: $(basename "$f")"
      rm -f "$f"
    done
  fi
}
prune "$DAILY_DIR" "$DAILY_KEEP"
prune "$WEEKLY_DIR" "$WEEKLY_KEEP"

# Yarim kalmis dosyalari topla (onceki basarisiz calismalardan).
find "$BACKUP_DIR" -name '*.partial' -mtime +1 -delete 2>/dev/null || true

log "Bitti. Toplam: $(du -sh "$BACKUP_DIR" | cut -f1)"
