"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Award } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";
import { marketTextClass } from "../../lib/marketColor";

interface LeaderboardItem {
  username: string;
  total_portfolio_value: number;
  profit_loss_pct: number;
  is_bot: boolean;
}

interface CategoryLeaderboardItem {
  username: string;
  deger: number;
  detay: string | null;
}

type Kategori = "getiri" | "istikrar" | "aktiflik" | "kahin";

const KATEGORI_SEKMELERI: { key: Kategori; label: string }[] = [
  { key: "getiri", label: "Getiri" },
  { key: "istikrar", label: "İstikrar" },
  { key: "aktiflik", label: "Aktiflik" },
  { key: "kahin", label: "Kâhin" },
];

const KATEGORI_BIRIM: Record<Kategori, (v: number) => string> = {
  getiri: (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`,
  istikrar: (v) => v.toFixed(2),
  aktiflik: (v) => `${Math.round(v)}`,
  kahin: (v) => `%${v.toFixed(0)}`,
};

/**
 * Ana sayfadaki liderlik tablosu kartı. "Getiri" mevcut (period destekli)
 * uçtan gelir; İstikrar/Aktiflik/Kâhin ise yeni /api/leaderboard/kategori
 * ucundan -- bu üçü yalnızca gerçek kullanıcıları kapsar (kişisel botlar
 * hariç), Kâhin ayrıca dönem sekmelerinden bağımsızdır (bkz. backend
 * leaderboard_categories.py).
 */
export default function LeaderboardWidget() {
  const { user } = useAuth();
  const [kategori, setKategori] = useState<Kategori>("getiri");
  const [period, setPeriod] = useState<"all" | "weekly" | "monthly">("all");
  const [getiriListesi, setGetiriListesi] = useState<LeaderboardItem[]>([]);
  const [kategoriListesi, setKategoriListesi] = useState<CategoryLeaderboardItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        if (kategori === "getiri") {
          const res = await fetch(`${API_BASE}/leaderboard?period=${period}`);
          if (res.ok && !cancelled) setGetiriListesi(await res.json());
        } else {
          const donemParam = kategori === "kahin" ? "" : `&period=${period}`;
          const res = await fetch(`${API_BASE}/leaderboard/kategori?category=${kategori}${donemParam}`);
          if (res.ok && !cancelled) setKategoriListesi(await res.json());
        }
      } catch (err) {
        console.error("Liderlik tablosu alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [kategori, period]);

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
      <div className="flex items-center gap-1.5 mb-3">
        <Award className="w-5 h-5 text-[#F59E0B]" />
        <h3 className="text-sm font-bold text-white tracking-wide uppercase">Liderlik Tablosu</h3>
      </div>

      <div className="flex items-center gap-1 mb-2 overflow-x-auto">
        {KATEGORI_SEKMELERI.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setKategori(opt.key)}
            className={`shrink-0 px-2.5 min-h-[32px] text-[11px] font-bold rounded-md transition ${
              kategori === opt.key ? "bg-[#10B981] text-[#0B0E14]" : "bg-[#0B0E14] text-gray-500 border border-[#242B35] hover:text-gray-300"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {kategori !== "kahin" && (
        <div className="flex items-center gap-1 mb-4 bg-[#0B0E14] border border-[#242B35] rounded-lg p-1">
          {([
            { key: "all", label: "Tümü" },
            { key: "weekly", label: "Bu Hafta" },
            { key: "monthly", label: "Bu Ay" },
          ] as const).map((opt) => (
            <button
              key={opt.key}
              onClick={() => setPeriod(opt.key)}
              className={`flex-1 min-h-[36px] text-[11px] font-semibold rounded-md transition ${
                period === opt.key ? "bg-[#242B35] text-white" : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      {kategori === "kahin" && <div className="mb-2" />}

      {loading ? (
        <p className="text-center py-6 text-gray-500 text-xs">Yükleniyor...</p>
      ) : kategori === "getiri" ? (
        <div className="space-y-3.5">
          {getiriListesi.map((player, idx) => (
            <div
              key={player.username}
              className={`flex items-center justify-between text-xs p-2.5 rounded-lg border ${
                user && (player.username === user.username || player.username === `${user.username} — Kişisel Bot`)
                  ? "bg-[#10B981]/10 border-[#10B981]/30 font-semibold"
                  : "bg-[#0B0E14] border-[#242B35]"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  idx === 0 ? "bg-[#F59E0B] text-[#0B0E14]" : idx === 1 ? "bg-slate-300 text-[#0B0E14]" : "bg-[#242B35] text-gray-400"
                }`}>
                  {idx + 1}
                </span>
                <div>
                  <span className="text-white flex items-center">
                    {player.is_bot ? (
                      player.username
                    ) : (
                      <Link href={`/profil/${player.username}`} className="hover:text-[#10B981] transition">
                        @{player.username}
                      </Link>
                    )}
                    {player.is_bot && (
                      <span className="ml-1 bg-[#F59E0B]/10 text-[#F59E0B] text-[8px] uppercase tracking-wider px-1 rounded font-bold">
                        BOT
                      </span>
                    )}
                  </span>
                  <span className="text-[10px] text-gray-500 tabular-nums">
                    {player.total_portfolio_value.toLocaleString("tr-TR")} TL
                  </span>
                </div>
              </div>
              <span className={`font-semibold tabular-nums ${marketTextClass(player.profit_loss_pct)}`}>
                {player.profit_loss_pct > 0 ? "+" : ""}{player.profit_loss_pct.toFixed(2)}%
              </span>
            </div>
          ))}
          {getiriListesi.length === 0 && <p className="text-center py-6 text-gray-500 text-xs">Henüz veri yok.</p>}
        </div>
      ) : (
        <div className="space-y-3.5">
          {kategoriListesi.map((player, idx) => (
            <div
              key={player.username}
              className={`flex items-center justify-between text-xs p-2.5 rounded-lg border ${
                user && player.username === user.username
                  ? "bg-[#10B981]/10 border-[#10B981]/30 font-semibold"
                  : "bg-[#0B0E14] border-[#242B35]"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  idx === 0 ? "bg-[#F59E0B] text-[#0B0E14]" : idx === 1 ? "bg-slate-300 text-[#0B0E14]" : "bg-[#242B35] text-gray-400"
                }`}>
                  {idx + 1}
                </span>
                <div>
                  <Link href={`/profil/${player.username}`} className="text-white hover:text-[#10B981] transition">
                    @{player.username}
                  </Link>
                  {player.detay && <span className="block text-[10px] text-gray-500 tabular-nums">{player.detay}</span>}
                </div>
              </div>
              <span className="font-semibold tabular-nums text-white">
                {KATEGORI_BIRIM[kategori](player.deger)}
              </span>
            </div>
          ))}
          {kategoriListesi.length === 0 && (
            <p className="text-center py-6 text-gray-500 text-xs">
              {kategori === "kahin" ? "Henüz yeterli sayıda çözümlenmiş tahmin yok." : "Bu dönemde henüz veri yok."}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
