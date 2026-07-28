"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Wallet, TrendingUp, Bot, PiggyBank, Flame } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { href: "/", label: "Portföy", icon: Wallet },
  { href: "/piyasalar", label: "BİST", icon: TrendingUp },
  { href: "/heatmap", label: "Isı Har.", icon: Flame },
  { href: "/bot", label: "Bot", icon: Bot },
  { href: "/fonlar", label: "Fonlar", icon: PiggyBank },
];

/**
 * Midas tarzı sabit alt gezinme çubuğu — yalnızca mobilde görünür (md:hidden),
 * tablet/masaüstünde NavBar üstteki gezinmeyi üstlenir. iOS'ta home-indicator
 * alanının üstüne binmemesi için safe-area-inset-bottom kadar ek padding uygulanır.
 */
export default function MobileBottomNav() {
  const pathname = usePathname() || "/";
  const { token } = useAuth();

  if (!token) return null;

  return (
    <nav
      className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-[#0B0E14]/95 backdrop-blur border-t border-[#242B35]"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="grid grid-cols-5">
        {NAV_LINKS.map((link) => {
          const Icon = link.icon;
          const isActive = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex flex-col items-center justify-center gap-1 py-2.5 min-h-[44px] text-[10px] font-semibold tracking-wide transition ${
                isActive ? "text-[#10B981]" : "text-gray-500 hover:text-white"
              }`}
            >
              <Icon className="w-5 h-5" strokeWidth={1.5} />
              {link.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
