import type { Metadata, Viewport } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "./context/AuthContext";
import NavBar from "./components/NavBar";
import Footer from "./components/Footer";
import OnboardingHelpModal from "./components/OnboardingHelpModal";
import MobileBottomNav from "./components/MobileBottomNav";
import CacheGuard from "./components/CacheGuard";
import InstallPrompt from "./components/InstallPrompt";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

export const metadata: Metadata = {
  title: "BIST Simülasyonu & Yapay Zeka Trader - Midas Deneyimi",
  description: "Borsa İstanbul 15 dakika gecikmeli verileri ile otonom çalışan yapay zeka trading simülasyonu ve arkadaş grubunuzla sanal portföy yarışı.",
  keywords: ["BIST", "Borsa Istanbul", "AI Trader", "Algoritmik Ticaret", "Sanal Portfoy", "Borsa Simulasyonu", "Midas"],
  // PWA: telefonda "Ana ekrana ekle" ile tam ekran uygulama gibi çalışır
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "BIST Sim",
  },
  icons: {
    icon: [
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
};

// Mobil tarayıcılarda input odaklandığında otomatik yakınlaştırmayı önlemek için
// globals.css'te tüm input/select/textarea öğelerine min. 16px font-size uygulanır
// (bkz. .tabular-nums yakınındaki kural) — burada userScalable kısıtlanmaz, erişilebilirlik
// için kullanıcının manuel yakınlaştırması her zaman serbest bırakılır.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "dark",
  themeColor: "#0B0E14",
  // iOS'ta ZORUNLU: viewport-fit=cover olmadan env(safe-area-inset-*) değerleri
  // her zaman 0 döner. Bu yüzden alt gezinme çubuğundaki safe-area dolgusu da
  // bu satır eklenene kadar hiçbir işe yaramıyordu. Ayrıca statusBarStyle
  // "black-translucent" olduğu için içerik çentiğin altına uzanır; üst/alt
  // dolgular NavBar ve MobileBottomNav içinde safe-area ile telafi edilir.
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr" suppressHydrationWarning>
      <body className={`${outfit.variable} antialiased bg-[#0B0E14]`} suppressHydrationWarning>
        {/*
          iOS'ta TAM EKRAN İÇİN ZORUNLU ETİKET.
          Next.js 16, `appleWebApp.capable: true` için yalnızca standartlaşmış
          <meta name="mobile-web-app-capable"> etiketini üretiyor; iOS Safari ise
          bu adı TANIMIYOR, hâlâ sadece apple- önekli olanı okuyor. Etiket
          olmadan ana ekrana eklenen simge tam ekran açılmaz, adres çubuklu bir
          Safari sekmesi olarak açılır ve status-bar ayarı da yok sayılır.
          metadata.other ile denendi, Next o anahtarı yok sayıyor. React 19
          <meta> öğelerini nerede render edilirse edilsin <head> içine taşıdığı
          için burada doğrudan yazılır.
        */}
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <AuthProvider>
          <CacheGuard />
          <div className="min-h-screen flex flex-col">
            <NavBar />
            {/* Sabit alt gezinme barinin yuksekligi + centikli cihazlarda alt guvenli
                alan. Onceki `pb-16` sabit 64px idi ve safe-area-inset-bottom'u
                hesaba katmiyordu; iPhone gibi cihazlarda sayfanin son satiri
                barin altinda kaliyordu. */}
            <div className="flex-1 pb-[calc(4.5rem+env(safe-area-inset-bottom))] md:pb-0">{children}</div>
            <Footer />
          </div>
          <MobileBottomNav />
          <InstallPrompt />
          <OnboardingHelpModal />
        </AuthProvider>
      </body>
    </html>
  );
}
