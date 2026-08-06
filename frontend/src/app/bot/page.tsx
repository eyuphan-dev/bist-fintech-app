import BotPageClient from "./BotPageClient";

// Next.js statik sayfalar icin uzun sureli (kismen "bayat" servis edilebilen)
// bir ic onbellek kullanir; Vercel'in CDN'i bunu her deploy'da otomatik
// temizler ama kendi sunucumuzda boyle bir mekanizma yok. Bu sayfanin icerigi
// zaten tamamen client-side (kullaniciya ozel, token'a bagli) oldugundan statik
// onbellekten fayda gormuyor, force-dynamic ile her istekte taze render alinir.
export const dynamic = "force-dynamic";

export default function BotPage() {
  return <BotPageClient />;
}
