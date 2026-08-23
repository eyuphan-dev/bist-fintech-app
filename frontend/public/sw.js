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
        // Yalnizca tam ve basarili yanitlar saklanir; kismi (206) veya hatali
        // yanitlarin onbellege girmesi bozuk sayfa yukleme sonucu verir.
        if (response && response.status === 200 && response.type === "basic") {
          const kopya = response.clone();
          // NE BEKLENIR NE DE waitUntil KULLANILIR:
          //  - await edilseydi sayfa, onbellege yazma bitene kadar dosyayi
          //    alamazdi; oysa yanit elimizde, yazma bir yan istir.
          //  - event.waitUntil() burada respondWith'in icinden cagriliyor ve
          //    tarayiciya gore olayin artik "etkin" sayilmadigi durumda
          //    InvalidStateError atar. Bu istisna respondWith sozunu reddeder
          //    ve DOSYA HIC YUKLENMEZ - onbellek suslemesi yuzunden sayfayi
          //    bozmak kabul edilemez. Bu yuzden hata yutulur.
          cache
            .put(request, kopya)
            .then(() => trimStaticCache())
            .catch(() => {});
        }
        return response;
      })()
    );
  }
});


// ---------------------------------------------------------------------------
// Web Push
// ---------------------------------------------------------------------------
// Alarm motoru sunucuda zaten calisiyordu; eksik olan teslimatti. Kullanici
// uygulamayi acmadan da alarmindan haberdar olsun diye bildirimler burada
// isletim sistemi bildirimi olarak gosterilir.
//
// iOS NOTU: Safari push'a yalnizca ANA EKRANA EKLENMIS (standalone) PWA'larda
// izin verir. Normal Safari sekmesinde abonelik hic kurulamaz; arayuz bu yuzden
// once kurulum ister.

self.addEventListener("push", (event) => {
  // Yuk cozulemezse bile bildirimi yutmayiz: kullaniciya genel bir bildirim
  // gostermek, hic gostermemekten iyidir.
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }

  const title = data.title || "BIST Simülasyonu";
  const options = {
    body: data.body || "Yeni bir bildiriminiz var.",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    // Ayni tag'li bildirimler ust uste yazilir; bir hisse icin arka arkaya
    // gelen alarmlar bildirim merkezini doldurmaz.
    tag: data.tag || "bist",
    // Tag ayni olsa bile yeni bildirim sessizce degistirmek yerine kullaniciyi
    // uyarsin - alarm bildirimi kacirilmamali.
    renotify: true,
    data: { url: data.url || "/" },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";

  event.waitUntil(
    (async () => {
      const clientList = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });

      // Uygulama zaten acikssa yeni sekme acmak yerine mevcut pencereyi one al
      // ve orada gezin; aksi halde her bildirim yeni bir sekme birakirdi.
      for (const client of clientList) {
        if (client.url.startsWith(self.location.origin)) {
          await client.focus();
          if ("navigate" in client) {
            try {
              await client.navigate(target);
            } catch {
              // Bazi tarayicilarda navigate engellenir; odaklanmis olmak yeter.
            }
          }
          return;
        }
      }

      await self.clients.openWindow(target);
    })()
  );
});
