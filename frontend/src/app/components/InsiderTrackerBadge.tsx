"use client";

import React, { useEffect, useState } from "react";
import { ArrowUpCircle, ArrowDownCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

interface InsiderTrade {
  id: number;
  symbol: string;
  title_person: string;
  trade_type: "ALIM" | "SATIM";
  quantity: number;
  price: number;
  trade_date: string;
}

interface InsiderTrackerBadgeProps {
  symbol: string;
}

/**
 * Son 90 gün içinde yönetici/patron alımı varsa "Patron Hissede Alımda!" rozetini gösterir.
 * Aksi halde hiçbir şey render etmez (sessiz bileşen).
 */
export default function InsiderTrackerBadge({ symbol }: InsiderTrackerBadgeProps) {
  const [trades, setTrades] = useState<InsiderTrade[]>([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchTrades = async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/insider-trades`);
        if (res.ok && !cancelled) {
          setTrades(await res.json());
        }
      } catch (err) {
        console.error("İçeriden öğrenenler verisi alınamadı:", err);
      }
    };
    fetchTrades();
    return () => {
      cancelled = true;
    };
  }, [symbol]);

  const recentBuys = trades.filter((t) => t.trade_type === "ALIM");
  const recentSells = trades.filter((t) => t.trade_type === "SATIM");

  if (recentBuys.length === 0 && recentSells.length === 0) return null;

  return (
    <div className="space-y-2">
      <button
        onClick={() => setExpanded((v) => !v)}
        className={`w-full flex items-center gap-2 rounded-lg px-3 py-2 border text-xs font-bold transition ${
          recentBuys.length > 0
            ? "bg-[#10B981]/10 border-[#10B981]/25 text-[#10B981]"
            : "bg-[#F43F5E]/10 border-[#F43F5E]/25 text-[#F43F5E]"
        }`}
      >
        {recentBuys.length > 0 ? (
          <>
            <ArrowUpCircle className="w-4 h-4" />
            Patron Hissede Alımda! ({recentBuys.length} işlem)
          </>
        ) : (
          <>
            <ArrowDownCircle className="w-4 h-4" />
            Yönetimden Satış Hareketi ({recentSells.length} işlem)
          </>
        )}
      </button>

      {expanded && (
        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-0.5">
          {trades.map((t) => (
            <div key={t.id} className="flex items-center justify-between bg-[#151921] border border-[#242B35] rounded-lg px-3 py-2 text-[11px]">
              <div>
                <p className="text-gray-300 font-medium">{t.title_person}</p>
                <p className="text-gray-500 text-[10px]">
                  {new Date(t.trade_date).toLocaleDateString("tr-TR")}
                </p>
              </div>
              <div className="text-right">
                <span className={`font-bold ${t.trade_type === "ALIM" ? "text-[#10B981]" : "text-[#F43F5E]"}`}>
                  {t.trade_type}
                </span>
                <p className="text-gray-400 tabular-nums">{t.quantity.toLocaleString("tr-TR")} adet</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
