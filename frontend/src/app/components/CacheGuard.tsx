"use client";

import { useEffect } from "react";

/**
 * Service worker kaydını yönetir.
 *
 * Bu bileşen eskiden İSTİSNASIZ tüm service worker'ları ve önbellekleri silerdi:
 * o dönemde projede hiç service worker yoktu ve amaç, eski denemelerden kalma
 * "hayalet" kayıtların siteyi eski bir sürümde donmuş göstermesini engellemekti.
 * Artık kendi service worker'ımız (/sw.js) olduğu için o davranış onu da anında
 * öldürürdü. Temizlik mantığı korunur ama hedefi daraltılır: BİZE AİT OLMAYAN
 * kayıtlar silinir, kendi kaydımız kurulur.
 */
export default function CacheGuard() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    // Yerel geliştirmede service worker devreye girerse Turbopack'in sıcak
    // yenilemesi ile karışır; yalnızca üretimde kaydedilir.
    const isProduction = process.env.NODE_ENV === "production";
    const OWN_SCRIPT = "/sw.js";

    (async () => {
      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        for (const reg of registrations) {
          const script = reg.active?.scriptURL || reg.installing?.scriptURL || reg.waiting?.scriptURL || "";
          const isOurs = script.endsWith(OWN_SCRIPT);
          // Üretimde yalnızca yabancı kayıtlar, geliştirmede hepsi silinir.
          if (!isOurs || !isProduction) {
            await reg.unregister();
          }
        }

        if (isProduction) {
          const reg = await navigator.serviceWorker.register(OWN_SCRIPT);
          // Uygulama her açıldığında güncelleme kontrolü yapılır; böylece yeni
          // sürüm en geç bir sonraki açılışta devreye girer.
          reg.update().catch(() => {});
        } else if ("caches" in window) {
          // Geliştirmede arta kalan önbellekleri tamamen temizle.
          const keys = await caches.keys();
          await Promise.all(keys.map((k) => caches.delete(k)));
        }
      } catch (err) {
        // Service worker olmadan da uygulama tamamen çalışır; sessizce geçilir.
        console.debug("Service worker kurulumu atlandı:", err);
      }
    })();
  }, []);

  return null;
}
