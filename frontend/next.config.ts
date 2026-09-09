import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build çıktısının yazılacağı dizin, ortam değişkeniyle geçici bir klasöre
  // yönlendirilebilsin diye dışarı açıldı.
  //
  // Neden: deploy sırasında `next build` çıktıyı doğrudan .next içine yazıyordu.
  // O sırada eski frontend süreci hâlâ istek karşıladığı için, altından değişen
  // dosyalar yüzünden TÜM sayfalar build boyunca (1-2 dk) 500 dönüyordu
  // ("Cannot find module .next/server/middleware-manifest.json").
  //
  // Deploy artık NEXT_DIST_DIR=.next-build ile derleyip bitince .next ile
  // yer değiştiriyor (mv). Böylece yıkıcı adım dakikalar değil milisaniyeler
  // sürüyor ve kesinti yalnızca pm2 restart anına iniyor.
  distDir: process.env.NEXT_DIST_DIR || ".next",

  async headers() {
    return [
      {
        // Tum sayfalara temel guvenlik basliklari. Content-Security-Policy
        // KASITLI OLARAK eklenmedi -- Next.js hydration/inline script
        // kullanimini bozma riski var ve nginx uzerinden ayri test edilmeden
        // uretimde denenmemeli. Burada sadece hicbir mesru kullanimi
        // bozmayan, sifir riskli standart baslikar var.
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
      {
        // Service worker betiği ASLA önbelleklenmemeli. Önbelleklenirse
        // tarayıcı eski sw.js'i tutar ve içindeki önbellek stratejisi
        // güncellenemez hale gelir — sunucudan düzeltmesi imkânsız bir
        // "eski sürümde donma" durumu doğar (nginx proxy_cache olayının
        // çok daha kalıcı hali). Aynı gerekçe manifest için de geçerli.
        source: "/:file(sw.js|manifest.webmanifest|offline.html)",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
        ],
      },
    ];
  },
};

export default nextConfig;
