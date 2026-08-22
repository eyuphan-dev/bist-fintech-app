/*
 * sw.js — BIST Simülasyonu service worker
 *
 * TASARIM İLKESİ — BAYAT İÇERİK ASLA SUNULMAZ:
 * Bu projede daha önce nginx'in global `proxy_cache` ayarı yüzünden kullanıcılara
 * eski arayüz sunuldu ve teşhisi günler aldı. Service worker aynı hatayı çok daha
 * kalıcı biçimde tekrarlayabilecek bir araçtır (tarayıcıda yaşar, sunucudan
 * temizlenemez). Bu yüzden burada bilinçli olarak DAR bir strateji uygulanır:
 *
 *   - HTML/sayfa gezinmeleri : SADECE AĞ. Çevrimdışıysa offline.html gösterilir.
 *                              Hiçbir koşulda önbellekten sayfa sunulmaz.
 *   - /api/*                 : HİÇ DOKUNULMAZ. Fiyat/portföy verisi bayat olamaz.
 *   - /_next/static/*        : Önbellek öncelikli. Bu dosyaların adında içerik
 *                              hash'i vardır; içeriği değişirse adı da değişir,
 *                              dolayısıyla bayatlaması teknik olarak imkânsızdır.
 *   - Diğer her şey          : Dokunulmaz, tarayıcıya bırakılır.
 *
 * Yani service worker'ın tek işi: uygulamayı çevrimdışı açılabilir kılmak ve
 * hash'li statik dosyaları tekrar indirtmemek. İçerik tazeliği tamamen ağa bağlı.
 *
 * ACİL DURDURMA: Service worker'ın sorun çıkardığı düşünülürse bu dosyayı
 * sunucudan SİLMEK yeterlidir. Tarayıcı bir sonraki güncelleme denemesinde 404
 * alınca kaydı kendiliğinden iptal eder ve önbellekleri temizler. Ayrıca
 * CacheGuard bileşenindeki register çağrısı da kaldırılmalıdır.
 */

const VERSION = "v1";
const STATIC_CACHE = `bist-static-${VERSION}`;
const SHELL_CACHE = `bist-shell-${VERSION}`;
const OWNED_CACHES = [STATIC_CACHE, SHELL_CACHE];

const OFFLINE_URL = "/offline.html";

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // reload: sunucudaki güncel kopyanın alınmasını garanti eder (HTTP
      // önbelleğinden eski bir offline.html gelmesin).
      await cache.add(new Request(OFFLINE_URL, { cache: "reload" }));
      // Yeni sürüm beklemeden devreye girsin — kullanıcı sekmeyi tamamen
      // kapatmadan da güncellemeyi alır.
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      // Eski sürümlerin ve bu SW'a ait olmayan önbelleklerin tamamı silinir.
      const keys = await caches.keys();
      await Promise.all(
        keys.filter((k) => !OWNED_CACHES.includes(k)).map((k) => caches.delete(k))
      );
      await trimStaticCache();
      await self.clients.claim();
    })()
  );
});

/**
 * Statik önbelleği sınırlar.
 *
 * /_next/static/ dosyalarının adında içerik hash'i olduğu için HER DEPLOY yeni
 * anahtarlar üretir ve eskiler kendiliğinden düşmez. Önbellek sürüm etiketi de
 * her deployda değişmediğinden, sınırlanmazsa onlarca deploy sonrasında
 * kullanıcının cihazında yüzlerce ölü dosya birikir. Kayıtlar ekleme sırasında
 * tutulduğu için en eskiler baştan silinir.
 */
const MAX_STATIC_ENTRIES = 160;

async function trimStaticCache() {
  const cache = await caches.open(STATIC_CACHE);
  const keys = await cache.keys();
  const excess = keys.length - MAX_STATIC_ENTRIES;
  if (excess > 0) {
    await Promise.all(keys.slice(0, excess).map((k) => cache.delete(k)));
  }
}

/** Yalnızca adında içerik hash'i olan, değişmez Next.js varlıkları. */
function isImmutableAsset(url) {
  return url.pathname.startsWith("/_next/static/");
}

self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (request.method !== "GET") return;

  let url;
  try {
    url = new URL(request.url);
  } catch {
    return;
  }

  // Farklı origin (API proxy'si, yazı tipleri vb.) ve tüm API çağrıları
  // service worker'a hiç uğramaz.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  // Sayfa gezinmeleri: ağ zorunlu, başarısızsa çevrimdışı sayfası.
  if (request.mode === "navigate") {
    event.respondWith(
      (async () => {
        try {
          return await fetch(request);
        } catch {
          const cache = await caches.open(SHELL_CACHE);
          const fallback = await cache.match(OFFLINE_URL);
          return (
            fallback ||
            new Response("Çevrimdışısınız.", {
              status: 503,
              headers: { "Content-Type": "text/plain; charset=utf-8" },
            })
          );
        }
      })()
    );
    return;
  }

  if (isImmutableAsset(url)) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(STATIC_CACHE);
        const hit = await cache.match(request);
        if (hit) return hit;
        const response = await fetch(request);
        // Yalnızca tam ve başarılı yanıtlar saklanır; kısmi (206) veya hatalı
        // yanıtların önbelleğe girmesi bozuk sayfa yükleme sonucu verir.
        if (response && response.status === 200 && response.type === "basic") {
          await cache.put(request, response.clone());
          // Budama yanıtı geciktirmesin diye beklenmez.
          event.waitUntil(trimStaticCache());
        }
        return response;
      })()
    );
  }
});
