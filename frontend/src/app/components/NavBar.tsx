"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  LineChart, Wallet, TrendingUp, Bot, PiggyBank, LogOut, Flame, CalendarDays,
  Star, SlidersHorizontal, MoreHorizontal, GitCompareArrows,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import NotificationBell from "./NotificationBell";
import GlobalStockSearch from "./GlobalStockSearch";

// En sık kullanılanlar her zaman görünür; geri kalanı "Daha Fazla" menüsüne
// toplanır — 8 öğenin tamamı tek satırda sığmayıp taşıyor, bazıları görünmüyordu.
const PRIMARY_NAV_LINKS = [
  { href: "/", label: "Portföyüm", icon: Wallet },
  { href: "/piyasalar", label: "Piyasalar", icon: TrendingUp },
  { href: "/favoriler", label: "Favorilerim", icon: Star },
  { href: "/tarayici", label: "Tarayıcı", icon: SlidersHorizontal },
  { href: "/bot", label: "AI Trader", icon: Bot },
];

const MORE_NAV_LINKS = [
  { href: "/karsilastir", label: "Hisse Karşılaştır", icon: GitCompareArrows },
  { href: "/heatmap", label: "Isı Haritası", icon: Flame },
  { href: "/takvim", label: "Bilanço & KAP Takvimi", icon: CalendarDays },
  { href: "/fonlar", label: "Fonlar & Halka Arz", icon: PiggyBank },
];

/** Sayfalar arası ana gezinme çubuğu. Route değişse de token/user AuthContext'ten okunur. */
export default function NavBar() {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { token, user, logout } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const isMoreActive = MORE_NAV_LINKS.some((l) => isActive(l.href));

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setMoreOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => setMoreOpen(false), [pathname]);

  if (!token) return null; // Giriş ekranında navbar gösterilmez

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  const linkClass = (active: boolean) =>
    `flex items-center gap-1.5 px-2.5 lg:px-3 py-2 rounded-lg text-xs font-semibold tracking-wide transition whitespace-nowrap shrink-0 ${
      active ? "bg-[#10B981] text-[#0B0E14]" : "text-gray-400 hover:text-white hover:bg-[#151921]"
    }`;

  return (
    <header className="border-b border-[#242B35] bg-[#0B0E14]/90 sticky top-0 z-30 backdrop-blur">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <LineChart className="w-6 h-6 text-[#10B981]" />
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
            <button onClick={() => setMoreOpen((v) => !v)} className={linkClass(isMoreActive || moreOpen)}>
              <MoreHorizontal className="w-3.5 h-3.5 shrink-0" />
              <span className="hidden lg:inline">Daha Fazla</span>
            </button>
            {moreOpen && (
              <div className="absolute top-full right-0 mt-1 w-56 bg-[#151921] border border-[#242B35] rounded-xl shadow-xl py-1.5 z-40">
                {MORE_NAV_LINKS.map((link) => {
                  const Icon = link.icon;
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold transition ${
                        isActive(link.href) ? "text-[#10B981]" : "text-gray-300 hover:text-white hover:bg-[#0B0E14]"
                      }`}
                    >
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

        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right hidden sm:block">
            <p className="text-[10px] text-gray-500">Hoş Geldiniz,</p>
            <p className="text-xs font-semibold text-white">@{user?.username}</p>
          </div>
          <NotificationBell />
          <button
            onClick={handleLogout}
            className="bg-[#151921] border border-[#242B35] hover:bg-[#242B35] hover:text-[#F43F5E] p-2 rounded-lg text-gray-400 transition"
            title="Güvenli Çıkış"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Mobilde arama, dar ekranda üst satıra sığmadığı için kendi satırında gösterilir */}
      <div className="md:hidden max-w-6xl mx-auto px-4 pb-2.5">
        <GlobalStockSearch />
      </div>
    </header>
  );
}
