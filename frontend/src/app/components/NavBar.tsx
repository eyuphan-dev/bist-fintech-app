"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LineChart, Wallet, TrendingUp, Bot, PiggyBank, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const NAV_LINKS = [
  { href: "/", label: "Portföyüm", icon: Wallet },
  { href: "/piyasalar", label: "Piyasalar", icon: TrendingUp },
  { href: "/bot", label: "Yapay Zeka Trader", icon: Bot },
  { href: "/fonlar", label: "Fonlar & Halka Arz", icon: PiggyBank },
];

/** Sayfalar arası ana gezinme çubuğu. Route değişse de token/user AuthContext'ten okunur. */
export default function NavBar() {
  const pathname = usePathname() || "/";
  const { token, user, logout } = useAuth();

  if (!token) return null; // Giriş ekranında navbar gösterilmez

  return (
    <header className="border-b border-[#242B35] bg-[#0B0E14]/90 sticky top-0 z-30 backdrop-blur">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <LineChart className="w-6 h-6 text-[#10B981]" />
          <span className="font-bold text-lg tracking-tight text-white hidden sm:inline">BIST Simülasyonu</span>
        </Link>

        <nav className="flex items-center gap-1 overflow-x-auto">
          {NAV_LINKS.map((link) => {
            const Icon = link.icon;
            const isActive = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold tracking-wide transition whitespace-nowrap ${
                  isActive
                    ? "bg-[#10B981] text-[#0B0E14]"
                    : "text-gray-400 hover:text-white hover:bg-[#151921]"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span className="hidden md:inline">{link.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right hidden sm:block">
            <p className="text-[10px] text-gray-500">Hoş Geldiniz,</p>
            <p className="text-xs font-semibold text-white">@{user?.username}</p>
          </div>
          <button
            onClick={logout}
            className="bg-[#151921] border border-[#242B35] hover:bg-[#242B35] hover:text-[#F43F5E] p-2 rounded-lg text-gray-400 transition"
            title="Güvenli Çıkış"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
