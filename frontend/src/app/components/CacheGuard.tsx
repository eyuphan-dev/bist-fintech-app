"use client";

import { useEffect } from "react";

// Bu proje hic service worker kullanmadi/kullanmiyor, ama bazi taraycilarda
// eski bir denemeden kalma "hayalet" bir service worker/Cache Storage kaydi
// varsa, siteyi eski bir surumde donduk gorunmesine sebep olabilir. Bu
// bileşen her ziyarette sessizce boyle bir kaydi temizler - zararsizdir,
// zaten kayit yoksa hicbir sey yapmaz.
export default function CacheGuard() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.getRegistrations().then((regs) => {
        regs.forEach((reg) => reg.unregister());
      });
    }
    if ("caches" in window) {
      caches.keys().then((keys) => {
        keys.forEach((key) => caches.delete(key));
      });
    }
  }, []);

  return null;
}
