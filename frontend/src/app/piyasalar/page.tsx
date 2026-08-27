"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Search, RefreshCw, Star } from "lucide-react";
import KatilimBadge from "../components/KatilimBadge";
import MarketQuotesBar from "../components/MarketQuotesBar";
import { useAuth, API_BASE } from "../context/AuthContext";
import { marketBadgeClass } from "../../lib/marketColor";

interface Stock {
  id: number;
  symbol: string;
  company_name: string;
  is_active: boolean;
  current_price: number;
  price_change_pct: number | null;
  is_katilim_compliant: boolean;
  katilim_status?: string | null;
  purification_rate: number;
}

export default function PiyasalarPage() {
  const { token, refreshTrigger } = useAuth();
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [katilimOnly, setKatilimOnly] = useState(false);
  const [watchedSymbols, setWatchedSymbols] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchStocks = async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks`);
        if (res.ok) setStocks(await res.json());
      } catch (err) {
        console.error("Hisse listesi alınamadı:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchStocks();
  }, [refreshTrigger]);

  useEffect(() => {
    if (!token) {
      setWatchedSymbols(new Set());
      return;
    }
    const fetchWatchlist = async () => {
      try {
        const res = await fetch(`${API_BASE}/watchlist`, { headers: { Authorization: `Bearer ${token}` } });
        if (res.ok) {
          const data: { symbol: string }[] = await res.json();
          setWatchedSymbols(new Set(data.map((d) => d.symbol)));
        }
      } catch (err) {
        console.error("İzleme listesi alınamadı:", err);
      }
    };
    fetchWatchlist();
  }, [token, refreshTrigger]);

  const toggleWatch = async (e: React.MouseEvent, symbol: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!token) return;
    const isWatched = watchedSymbols.has(symbol);
    try {
      const res = await fetch(`${API_BASE}/watchlist/${symbol}`, {
        method: isWatched ? "DELETE" : "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setWatchedSymbols((prev) => {
          const next = new Set(prev);
          if (isWatched) next.delete(symbol);
          else next.add(symbol);
          return next;
        });
      }
    } catch (err) {
      console.error("İzleme listesi güncellenemedi:", err);
    }
  };

  const filteredStocks = stocks.filter((s) => {
    const matchesQuery =
      s.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.company_name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesKatilim = !katilimOnly || s.is_katilim_compliant;
    return matchesQuery && matchesKatilim;
  });

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Piyasalar</h1>
        <p className="text-xs text-gray-500 mt-1">BİST hisselerini inceleyin, Katılım Endeksi uygunluğunu görün.</p>
      </div>

      <MarketQuotesBar />

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-3.5" />
          <input
            type="text"
            placeholder="Hisse sembolü veya şirket adı ara..."
            className="w-full bg-[#151921] border border-[#242B35] focus:border-[#4A87C7] rounded-xl pl-10 pr-4 py-2.5 text-white outline-none transition text-sm"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <button
          onClick={() => setKatilimOnly((v) => !v)}
          className={`px-4 py-2.5 rounded-xl text-xs font-bold border transition whitespace-nowrap ${
            katilimOnly
              ? "bg-[#4A87C7]/10 border-[#4A87C7]/30 text-[#4A87C7]"
              : "bg-[#151921] border-[#242B35] text-gray-400 hover:text-white"
          }`}
        >
          Yalnızca Katılım Uygun
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#4A87C7]" />
          Hisseler yükleniyor...
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredStocks.map((stock) => (
            <Link
              key={stock.symbol}
              href={`/hisse/${stock.symbol}`}
              className="bg-[#151921] p-4 rounded-2xl border border-[#242B35] hover:border-[#4A87C7]/40 transition flex flex-col gap-3 relative"
            >
              {token && (
                <button
                  onClick={(e) => toggleWatch(e, stock.symbol)}
                  title={watchedSymbols.has(stock.symbol) ? "Favorilerden çıkar" : "Favorilere ekle"}
                  // İkon 16x16 kalır ama dokunma alanı 44x44'e çıkarılır (-m ile
                  // görsel konum korunur). Liste kartlarında sık kullanılan bir
                  // kontrol olduğu için parmakla ıskalanması can sıkıcıydı.
                  className={`absolute top-3 right-3 -m-3 p-3 min-w-[44px] min-h-[44px] flex items-start justify-end transition ${
                    watchedSymbols.has(stock.symbol) ? "text-[#F59E0B]" : "text-gray-600 hover:text-[#F59E0B]"
                  }`}
                >
                  <Star className="w-4 h-4" fill={watchedSymbols.has(stock.symbol) ? "currentColor" : "none"} />
                </button>
              )}
              <div className="flex items-start justify-between pr-6">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white tracking-wide">{stock.symbol}</span>
                    {stock.price_change_pct !== null ? (
                      <span className={`text-[10px] font-semibold px-1 rounded tabular-nums ${
                        marketBadgeClass(stock.price_change_pct)
                      }`}>
                        %{stock.price_change_pct > 0 ? "+" : ""}{stock.price_change_pct}
                      </span>
                    ) : (
                      <span
                        title="Kurumsal işlem (bölünme/bedelsiz sermaye artışı) nedeniyle günlük değişim şu an güvenilir hesaplanamıyor."
                        className="text-[10px] font-semibold px-1 rounded tabular-nums bg-gray-500/10 text-gray-500"
                      >
                        —
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-500 mt-0.5 truncate max-w-[180px]">{stock.company_name}</p>
                </div>
                <p className="font-bold text-sm text-white tabular-nums">{stock.current_price} TL</p>
              </div>

              <div onClick={(e) => e.stopPropagation()} className="w-fit">
                <KatilimBadge
                  isCompliant={stock.is_katilim_compliant}
                  status={stock.katilim_status}
                  purificationRate={stock.purification_rate}
                  size="sm"
                />
              </div>
            </Link>
          ))}

          {filteredStocks.length === 0 && (
            <p className="col-span-full text-center text-gray-500 text-xs py-10">Aramanızla eşleşen hisse bulunamadı.</p>
          )}
        </div>
      )}
    </div>
  );
}
