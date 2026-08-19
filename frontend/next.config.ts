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
};

export default nextConfig;
