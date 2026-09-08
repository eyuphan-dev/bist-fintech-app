"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Wallet, TrendingUp, Bot, PiggyBank, Flame, Menu, X, Star, History,
  Settings, SlidersHorizontal, GitCompareArrows, CalendarDays, LogOut, Radar, Layers,
  ShoppingBasket, Rewind, Trophy, Calculator, Crown,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

// Alt barda yalnızca en sık kullanılan 4 sayfa durur; 5. slot "Menü".
const NAV_LINKS = [
  { href: "/", label: "Portföy", icon: Wallet },
  { href: "/piyasalar", label: "BİST", icon: TrendingUp },
  { href: "/bot", label: "Bot", icon: Bot },
  { href: "/fonlar", label: "Fonlar", icon: PiggyBank },
];

// Üst gezinme mobilde gizli (hidden md:flex) olduğundan, alt barda yer almayan
// sayfalara mobilde ULAŞILAMIYORDU. Bu sayfaların tamamı aşağıdaki menüde toplanır.
const MENU_GROUPS: {
  title: string;
  links: { href: string; label: string; icon: React.ElementType }[];
}[] = [
  {
    title: "Piyasa",
    links: [
      { href: "/tarayici", label: "Tarayıcı", icon: SlidersHorizontal },
      { href: "/sinyaller", label: "Teknik Sinyaller", icon: Radar },
      { href: "/sampiyonlar", label: "Şampiyonlar Duvarı", icon: Crown },
      { href: "/sepetler", label: "Tematik Sepetler", icon: ShoppingBasket },
      { href: "/replay", label: "Replay Modu", icon: Rewind },
      { href: "/risk-hesaplayici", label: "Risk Hesaplayıcı", icon: Calculator },
      { href: "/sektorler", label: "Sektör Analizi", icon: Layers },
      { href: "/karsilastir", label: "Hisse Karşılaştır", icon: GitCompareArrows },
      { href: "/heatmap", label: "Isı Haritası", icon: Flame },
      { href: "/takvim", label: "Bilanço & KAP Takvimi", icon: CalendarDays },
    ],
  },
  {
    title: "Hesabım",
    links: [
      { href: "/favoriler", label: "Favori Hisselerim", icon: Star },
      { href: "/islemlerim", label: "İşlem Geçmişim", icon: History },
      { href: "/basarimlar", label: "Başarımlarım", icon: Trophy },
      { href: "/ayarlar", label: "Hesap Ayarları", icon: Settings },
    ],
  },
];

/**
 * Midas tarzı sabit alt gezinme çubuğu — yalnızca mobilde görünür (md:hidden),
 * tablet/masaüstünde NavBar üstteki gezinmeyi üstlenir. iOS'ta home-indicator
 * alanının üstüne binmemesi için safe-area-inset-bottom kadar ek padding uygulanır.
 */
export default function MobileBottomNav() {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const { token, user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  // Route değişince menü kapanır (kullanıcı bir bağlantıya tıkladığında).
  useEffect(() => setMenuOpen(false), [pathname]);

  // Menü açıkken arka planın kaydırılmasını engelle — açık sayfanın altındaki
  // içerik kayarsa menü kapandığında kullanıcı farklı bir yerde buluyor kendini.
  useEffect(() => {
    if (!menuOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [menuOpen]);

  useEffect(() => {
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, []);

  if (!token) return null;

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const isMenuActive = MENU_GROUPS.some((g) => g.links.some((l) => isActive(l.href)));

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
    router.push("/");
  };

  const itemClass = (active: boolean) =>
    `flex flex-col items-center justify-center gap-1 py-2.5 min-h-[44px] text-[10px] font-semibold tracking-wide transition ${
      active ? "text-[#10B981]" : "text-gray-500 hover:text-white"
    }`;

  return (
    <>
      {/* Tam ekran menü */}
      {menuOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex flex-col bg-[#0B0E14]">
          <div className="flex items-center justify-between px-4 h-16 border-b border-[#242B35] shrink-0">
            <div className="flex items-center gap-2.5 min-w-0">
              <span className="w-9 h-9 rounded-full bg-[#10B981] text-[#0B0E14] font-bold text-sm flex items-center justify-center shrink-0">
                {(user?.username?.[0] ?? "?").toUpperCase()}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-bold text-white truncate">@{user?.username}</p>
                {user?.email && <p className="text-[10px] text-gray-500 truncate">{user.email}</p>}
              </div>
            </div>
            <button
              onClick={() => setMenuOpen(false)}
              className="p-2.5 -mr-2.5 min-w-[44px] min-h-[44px] flex items-center justify-center text-gray-400 hover:text-white transition"
              aria-label="Menüyü kapat"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div
            className="flex-1 overflow-y-auto px-4 py-4 space-y-5"
            style={{ paddingBottom: "calc(1rem + env(safe-area-inset-bottom))" }}
          >
            {MENU_GROUPS.map((group) => (
              <div key={group.title}>
                <p className="text-[10px] font-bold text-gray-600 uppercase tracking-wider px-1 mb-1.5">
                  {group.title}
                </p>
                <div className="bg-[#151921] border border-[#242B35] rounded-xl overflow-hidden">
                  {group.links.map((link, i) => {
                    const Icon = link.icon;
                    const active = isActive(link.href);
                    return (
                      <Link
                        key={link.href}
                        href={link.href}
                        className={`flex items-center gap-3 px-4 min-h-[52px] text-sm font-semibold transition ${
                          i > 0 ? "border-t border-[#242B35]" : ""
                        } ${active ? "text-[#10B981] bg-[#10B981]/5" : "text-gray-200 active:bg-[#0B0E14]"}`}
                      >
                        <Icon className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                        {link.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}

            <button
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-2 min-h-[52px] bg-[#151921] border border-[#242B35] rounded-xl text-sm font-semibold text-gray-300 active:text-[#F43F5E] transition"
            >
              <LogOut className="w-4 h-4" strokeWidth={1.5} />
              Güvenli Çıkış
            </button>
          </div>
        </div>
      )}

      <nav
        className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-[#0B0E14]/95 backdrop-blur border-t border-[#242B35]"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      >
        <div className="grid grid-cols-5">
          {NAV_LINKS.map((link) => {
            const Icon = link.icon;
            return (
              <Link key={link.href} href={link.href} className={itemClass(isActive(link.href))}>
                <Icon className="w-5 h-5" strokeWidth={1.5} />
                {link.label}
              </Link>
            );
          })}

          <button
            onClick={() => setMenuOpen(true)}
            className={itemClass(isMenuActive || menuOpen)}
            aria-label="Menüyü aç"
            aria-expanded={menuOpen}
          >
            <Menu className="w-5 h-5" strokeWidth={1.5} />
            Menü
          </button>
        </div>
      </nav>
    </>
  );
}
