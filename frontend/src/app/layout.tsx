import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "./context/AuthContext";
import NavBar from "./components/NavBar";
import Footer from "./components/Footer";
import OnboardingHelpModal from "./components/OnboardingHelpModal";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
});

export const metadata: Metadata = {
  title: "BIST Simülasyonu & Yapay Zeka Trader - Midas Deneyimi",
  description: "Borsa İstanbul 15 dakika gecikmeli verileri ile otonom çalışan yapay zeka trading simülasyonu ve arkadaş grubunuzla sanal portföy yarışı.",
  keywords: ["BIST", "Borsa Istanbul", "AI Trader", "Algoritmik Ticaret", "Sanal Portfoy", "Borsa Simulasyonu", "Midas"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr">
      <body className={`${outfit.variable} antialiased bg-[#0B0E14]`}>
        <AuthProvider>
          <div className="min-h-screen flex flex-col">
            <NavBar />
            <div className="flex-1">{children}</div>
            <Footer />
          </div>
          <OnboardingHelpModal />
        </AuthProvider>
      </body>
    </html>
  );
}
