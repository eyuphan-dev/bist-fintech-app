"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw, Star, StarOff } from "lucide-react";
import KatilimBadge from "../components/KatilimBadge";
import { useAuth, API_BASE } from "../context/AuthContext";

interface WatchlistItem {
  symbol: string;
  company_name: string;
  current_price: number;
  price_change_pct: number | null;
  is_katilim_compliant: boolean;
  purification_rate: number;
  added_at: string;
}

export default function FavorilerPage() {
  const { token, refreshTrigger } = useAuth();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null);

  const fetchWatchlist = async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/watchlist`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setItems(await res.json());
    } catch (err) {
      console.error("İzleme listesi alınamadı:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWatchlist();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshTrigger]);

  const handleRemove = async (symbol: string) => {
    if (!token) return;
    setRemoving(symbol);
    try {
      const res = await fetch(`${API_BASE}/watchlist/${symbol}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setItems((prev) => prev.filter((i) => i.symbol !== symbol));
    } catch (err) {
      console.error("İzleme listesinden çıkarılamadı:", err);
    } finally {
      setRemoving(null);
    }
  };

  if (!token) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-16 text-center text-gray-500 text-sm">
        Favori hisselerinizi görmek için giriş yapmalısınız.
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Star className="w-5 h-5 text-[#F59E0B]" /> Favorilerim
        </h1>
        <p className="text-xs text-gray-500 mt-1">İzlemek için yıldızladığınız hisseler burada listelenir.</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
          Favoriler yükleniyor...
        </div>
      ) : items.length === 0 ? (
        <div className="text-center text-gray-500 text-xs py-16 space-y-2">
          <p>Henüz favori hisseniz yok.</p>
          <Link href="/piyasalar" className="text-[#10B981] font-semibold hover:text-[#34d399]">
            Piyasalara göz atın →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <div
              key={item.symbol}
              className="bg-[#151921] p-4 rounded-2xl border border-[#242B35] hover:border-[#10B981]/40 transition flex flex-col gap-3 relative"
            >
              <button
                onClick={() => handleRemove(item.symbol)}
                disabled={removing === item.symbol}
                title="Favorilerden çıkar"
                className="absolute top-3 right-3 text-[#F59E0B] hover:text-[#F43F5E] transition disabled:opacity-50"
              >
                {removing === item.symbol ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <StarOff className="w-4 h-4" />
                )}
              </button>

              <Link href={`/hisse/${item.symbol}`} className="flex flex-col gap-3">
                <div className="flex items-start justify-between pr-6">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-white tracking-wide">{item.symbol}</span>
                      {item.price_change_pct !== null ? (
                        <span className={`text-[10px] font-semibold px-1 rounded tabular-nums ${
                          item.price_change_pct >= 0 ? "bg-[#10B981]/10 text-[#10B981]" : "bg-[#F43F5E]/10 text-[#F43F5E]"
                        }`}>
                          %{item.price_change_pct >= 0 ? "+" : ""}{item.price_change_pct}
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold px-1 rounded tabular-nums bg-gray-500/10 text-gray-500">—</span>
                      )}
                    </div>
                    <p className="text-[11px] text-gray-500 mt-0.5 truncate max-w-[180px]">{item.company_name}</p>
                  </div>
                  <p className="font-bold text-sm text-white tabular-nums">{item.current_price} TL</p>
                </div>

                <KatilimBadge isCompliant={item.is_katilim_compliant} purificationRate={item.purification_rate} size="sm" />
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
