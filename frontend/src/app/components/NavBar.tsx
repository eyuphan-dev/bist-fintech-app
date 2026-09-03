"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LineChart, Wallet, TrendingUp, Bot, PiggyBank, LogOut, Flame, CalendarDays,
  Star, SlidersHorizontal, MoreHorizontal, GitCompareArrows, History, Settings,
  ChevronDown, Radar, Layers, ShoppingBasket, Rewind, Trophy, Calculator,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import NotificationBell from "./NotificationBell";
import GlobalStockSearch from "./GlobalStockSearch";

// Piyasa/araç sayfaları üst gezinmede kalır. Kişisel sayfalar (favoriler, işlem
// geçmişi, ayarlar) buradan çıkarılıp kullanıcı menüsüne taşındı — üst çubuk
// aksi halde 8+ sekmeyle taşıyordu.
const PRIMARY_NAV_LINKS = [
  { href: "/", label: "Portföyüm", icon: Wallet },
  { href: "/piyasalar", label: "Piyasalar", icon: TrendingUp },
  { href: "/tarayici", label: "Tarayıcı", icon: SlidersHorizontal },
  { href: "/bot", label: "AI Trader", icon: Bot },
];

const MORE_NAV_LINKS = [
  { href: "/sinyaller", label: "Teknik Sinyaller", icon: Radar },
  { href: "/sepetler", label: "Tematik Sepetler", icon: ShoppingBasket },
  { href: "/replay", label: "Replay Modu", icon: Rewind },
  { href: "/risk-hesaplayici", label: "Risk Hesaplayıcı", icon: Calculator },
  { href: "/sektorler", label: "Sektör Analizi", icon: Layers },
  { href: "/karsilastir", label: "Hisse Karşılaştır", icon: GitCompareArrows },
  { href: "/heatmap", label: "Isı Haritası", icon: Flame },
  { href: "/takvim", label: "Bilanço & KAP Takvimi", icon: CalendarDays },
  { href: "/fonlar", label: "Fonlar & Halka Arz", icon: PiggyBank },
];

// Kullanıcı ikonunun altında açılan kişisel alan.
const USER_MENU_LINKS = [
  { href: "/favoriler", label: "Favori Hisselerim", icon: Star },
  { href: "/islemlerim", label: "İşlem Geçmişim", icon: History },
  { href: "/basarimlar", label: "Başarımlarım", icon: Trophy },
  { href: "/ayarlar", label: "Hesap Ayarları", icon: Settings },
];

/** Sayfalar arası ana gezinme çubuğu. Route değişse de token/user AuthContext'ten okunur. */
export default function NavBar() {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { token, user, logout } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const isMoreActive = MORE_NAV_LINKS.some((l) => isActive(l.href));
  const isUserActive = USER_MENU_LINKS.some((l) => isActive(l.href));

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
      if (userRef.current && !userRef.current.contains(e.target as Node)) setUserOpen(false);
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMoreOpen(false);
        setUserOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  useEffect(() => {
    setMoreOpen(false);
    setUserOpen(false);
  }, [pathname]);

  // Giriş ekranında navbar gösterilmez. Yine de çentik yüksekliğinde bir ayraç
  // bırakılır: statusBarStyle "black-translucent" olduğu için iOS'ta içerik
  // durum çubuğunun ALTINA uzanır ve navbar olmadığı için giriş formunun üstü
  // saatin/pilin arkasında kalırdı.
  if (!token) return <div aria-hidden style={{ height: "env(safe-area-inset-top)" }} />;

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  const linkClass = (active: boolean) =>
    `flex items-center gap-1.5 px-2.5 lg:px-3 py-2 rounded-lg text-xs font-semibold tracking-wide transition whitespace-nowrap shrink-0 ${
      active ? "bg-[#10B981] text-[#0B0E14]" : "text-gray-400 hover:text-white hover:bg-[#151921]"
    }`;

  const dropdownItemClass = (active: boolean) =>
    `flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold transition ${
      active ? "text-[#10B981]" : "text-gray-300 hover:text-white hover:bg-[#0B0E14]"
    }`;

  // Safe-area dolgusu header'IN İÇİNDE uygulanır: böylece çubuğun arka planı
  // durum çubuğunun arkasını da boyar, içerik ise çentiğin altından başlar.
  return (
    <header
      className="border-b border-[#242B35] bg-[#0B0E14]/90 sticky top-0 z-30 backdrop-blur"
      style={{ paddingTop: "env(safe-area-inset-top)" }}
    >
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 shrink-0 min-h-[44px] md:min-h-0 -ml-1 pl-1 pr-1 md:ml-0 md:px-0">
          <span className="w-8 h-8 rounded-lg bg-[#C46D2C] flex items-center justify-center shrink-0">
            <LineChart className="w-5 h-5 text-white" />
          </span>
          <span className="font-bold text-lg tracking-tight text-white hidden sm:inline">BIST Simülasyonu</span>
        </Link>

        <nav className="hidden md:flex items-center gap-0.5 lg:gap-1">
          {PRIMARY_NAV_LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <Link key={link.href} href={link.href} title={link.label} className={linkClass(isActive(link.href))}>
                <Icon className="w-3.5 h-3.5 shrink-0" />
                <span className="hidden lg:inline">{link.label}</span>
              </Link>
            );
          })}

          <div className="relative" ref={moreRef}>
            <button
              onClick={() => { setMoreOpen((v) => !v); setUserOpen(false); }}
              className={linkClass(isMoreActive || moreOpen)}
              aria-haspopup="true"
              aria-expanded={moreOpen}
            >
              <MoreHorizontal className="w-3.5 h-3.5 shrink-0" />
              <span className="hidden lg:inline">Daha Fazla</span>
            </button>
            {moreOpen && (
              <div className="absolute top-full right-0 mt-1 w-56 bg-[#151921] border border-[#242B35] rounded-xl py-1.5 z-40">
                {MORE_NAV_LINKS.map((link) => {
                  const Icon = link.icon;
                  return (
                    <Link key={link.href} href={link.href} className={dropdownItemClass(isActive(link.href))}>
                      <Icon className="w-3.5 h-3.5 shrink-0" />
                      {link.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </nav>

        {/* Masaüstünde arama kutusu navigasyon ile kullanıcı bloğu arasında durur */}
        <div className="hidden md:block flex-1 max-w-xs">
          <GlobalStockSearch />
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <NotificationBell />

          {/* Kullanıcı menüsü — kişisel sayfalar ve çıkış burada toplanır */}
          <div className="relative" ref={userRef}>
            <button
              onClick={() => { setUserOpen((v) => !v); setMoreOpen(false); }}
              className={`flex items-center gap-1.5 rounded-lg pl-1 pr-1.5 py-1 transition min-h-[44px] md:min-h-0 ${
                isUserActive || userOpen ? "bg-[#151921]" : "hover:bg-[#151921]"
              }`}
              aria-haspopup="true"
              aria-expanded={userOpen}
              title="Hesabım"
            >
              <span className="w-8 h-8 rounded-full bg-[#10B981] text-[#0B0E14] font-bold text-sm flex items-center justify-center shrink-0">
                {(user?.username?.[0] ?? "?").toUpperCase()}
              </span>
              <ChevronDown
                className={`w-3.5 h-3.5 text-gray-500 transition-transform ${userOpen ? "rotate-180" : ""}`}
              />
            </button>

            {userOpen && (
              <div className="absolute top-full right-0 mt-1 w-60 bg-[#151921] border border-[#242B35] rounded-xl py-1.5 z-40">
                <div className="px-3.5 pt-1 pb-2.5 border-b border-[#242B35] mb-1.5">
                  <p className="text-[10px] text-gray-500">Giriş yapıldı</p>
                  <p className="text-xs font-bold text-white truncate">@{user?.username}</p>
                  {user?.email && (
                    <p className="text-[10px] text-gray-500 truncate mt-0.5">{user.email}</p>
                  )}
                </div>

                {USER_MENU_LINKS.map((link) => {
                  const Icon = link.icon;
                  return (
                    <Link key={link.href} href={link.href} className={dropdownItemClass(isActive(link.href))}>
                      <Icon className="w-3.5 h-3.5 shrink-0" />
                      {link.label}
                    </Link>
                  );
                })}

                <div className="border-t border-[#242B35] mt-1.5 pt-1.5">
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold text-gray-300 hover:text-[#F43F5E] hover:bg-[#0B0E14] transition"
                  >
                    <LogOut className="w-3.5 h-3.5 shrink-0" />
                    Güvenli Çıkış
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobilde arama, dar ekranda üst satıra sığmadığı için kendi satırında gösterilir */}
      <div className="md:hidden max-w-6xl mx-auto px-4 pb-2.5">
        <GlobalStockSearch />
      </div>
    </header>
  );
}
