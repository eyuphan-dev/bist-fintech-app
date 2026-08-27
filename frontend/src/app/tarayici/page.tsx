"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { RefreshCw, SlidersHorizontal, ArrowUp, ArrowDown, X } from "lucide-react";
import KatilimBadge from "../components/KatilimBadge";
import { API_BASE } from "../context/AuthContext";
import { marketTextClass } from "../../lib/marketColor";

interface ScreenerItem {
  symbol: string;
  company_name: string;
  sector: string | null;
  current_price: number;
  price_change_pct: number | null;
  is_katilim_compliant: boolean;
  katilim_status?: string | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  roe: number | null;
  piotroski_score: number | null;
  dividend_yield: number | null;
  target_upside_pct: number | null;
  altman_z_score: number | null;
  debt_to_equity: number | null;
  net_margin: number | null;
}

type SortField = "price_change_pct" | "pe_ratio" | "pb_ratio" | "roe" | "piotroski_score" | "current_price" | "dividend_yield" | "target_upside_pct";

const SORT_OPTIONS: { value: SortField; label: string }[] = [
  { value: "price_change_pct", label: "Günlük Değişim" },
  { value: "pe_ratio", label: "F/K Oranı" },
  { value: "pb_ratio", label: "PD/DD Oranı" },
  { value: "roe", label: "Özkaynak Kârlılığı (ROE)" },
  { value: "piotroski_score", label: "Piotroski Skoru" },
  { value: "dividend_yield", label: "Temettü Verimi" },
  { value: "target_upside_pct", label: "Analist Potansiyeli" },
  { value: "current_price", label: "Fiyat" },
];

const EMPTY_FILTERS = {
  sector: "",
  katilimOnly: false,
  minPe: "",
  maxPe: "",
  minPb: "",
  maxPb: "",
  minRoe: "",
  minPiotroski: "",
  minDividendYield: "",
};

export default function TarayiciPage() {
  const [items, setItems] = useState<ScreenerItem[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortField>("price_change_pct");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [filters, setFilters] = useState(EMPTY_FILTERS);

  // Sektör listesini bir kez /api/stocks'tan türet
  useEffect(() => {
    const fetchSectors = async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks`);
        if (res.ok) {
          const data: { sector: string | null }[] = await res.json();
          const unique = Array.from(new Set(data.map((d) => d.sector).filter(Boolean))) as string[];
          setSectors(unique.sort((a, b) => a.localeCompare(b)));
        }
      } catch (err) {
        console.error("Sektör listesi alınamadı:", err);
      }
    };
    fetchSectors();
  }, []);

  const fetchScreener = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ sort_by: sortBy, order });
      if (filters.sector) params.set("sector", filters.sector);
      if (filters.katilimOnly) params.set("katilim_only", "true");
      if (filters.minPe) params.set("min_pe", filters.minPe);
      if (filters.maxPe) params.set("max_pe", filters.maxPe);
      if (filters.minPb) params.set("min_pb", filters.minPb);
      if (filters.maxPb) params.set("max_pb", filters.maxPb);
      if (filters.minRoe) params.set("min_roe", filters.minRoe);
      if (filters.minPiotroski) params.set("min_piotroski", filters.minPiotroski);
      if (filters.minDividendYield) params.set("min_dividend_yield", filters.minDividendYield);

      const res = await fetch(`${API_BASE}/screener?${params.toString()}`);
      if (res.ok) setItems(await res.json());
    } catch (err) {
      console.error("Tarayıcı verisi alınamadı:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScreener();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortBy, order]);

  const activeFilterCount = useMemo(
    () => Object.entries(filters).filter(([k, v]) => (k === "katilimOnly" ? v === true : v !== "")).length,
    [filters]
  );

  const fmt = (v: number | null, suffix = "") => (v === null || v === undefined ? "—" : `${v}${suffix}`);

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <SlidersHorizontal className="w-5 h-5 text-[#10B981]" /> Hisse Tarayıcı
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          F/K, PD/DD, ROE, Piotroski skoru, temettü verimi ve sektöre göre filtreleyip sıralayın.
        </p>
      </div>

      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">Sektör</label>
            <select
              value={filters.sector}
              onChange={(e) => setFilters((f) => ({ ...f, sector: e.target.value }))}
              className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2.5 py-3 md:py-2 text-white text-xs outline-none"
            >
              <option value="">Tümü</option>
              {sectors.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">F/K (min-max)</label>
            <div className="flex gap-1 mt-1">
              <input type="number" placeholder="Min" value={filters.minPe} onChange={(e) => setFilters((f) => ({ ...f, minPe: e.target.value }))}
                className="w-1/2 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2 py-2 text-white text-xs outline-none" />
              <input type="number" placeholder="Max" value={filters.maxPe} onChange={(e) => setFilters((f) => ({ ...f, maxPe: e.target.value }))}
                className="w-1/2 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2 py-2 text-white text-xs outline-none" />
            </div>
          </div>

          <div>
            <label className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">PD/DD (min-max)</label>
            <div className="flex gap-1 mt-1">
              <input type="number" placeholder="Min" value={filters.minPb} onChange={(e) => setFilters((f) => ({ ...f, minPb: e.target.value }))}
                className="w-1/2 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2 py-2 text-white text-xs outline-none" />
              <input type="number" placeholder="Max" value={filters.maxPb} onChange={(e) => setFilters((f) => ({ ...f, maxPb: e.target.value }))}
                className="w-1/2 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2 py-2 text-white text-xs outline-none" />
            </div>
          </div>

          <div>
            <label className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">Min. ROE (%)</label>
            <input type="number" placeholder="örn. 15" value={filters.minRoe} onChange={(e) => setFilters((f) => ({ ...f, minRoe: e.target.value }))}
              className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2.5 py-3 md:py-2 text-white text-xs outline-none" />
          </div>

          <div>
            <label className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">Min. Piotroski (0-9)</label>
            <input type="number" min={0} max={9} placeholder="örn. 6" value={filters.minPiotroski} onChange={(e) => setFilters((f) => ({ ...f, minPiotroski: e.target.value }))}
              className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2.5 py-3 md:py-2 text-white text-xs outline-none" />
          </div>

          <div>
            <label className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">Min. Temettü Verimi (%)</label>
            <input type="number" min={0} step="0.5" placeholder="örn. 3" value={filters.minDividendYield} onChange={(e) => setFilters((f) => ({ ...f, minDividendYield: e.target.value }))}
              className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2.5 py-3 md:py-2 text-white text-xs outline-none" />
          </div>

          <div className="flex items-end">
            <button
              onClick={() => setFilters((f) => ({ ...f, katilimOnly: !f.katilimOnly }))}
              className={`w-full px-3 py-2 rounded-lg text-xs font-bold border transition ${
                filters.katilimOnly
                  ? "bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]"
                  : "bg-[#0B0E14] border-[#242B35] text-gray-400 hover:text-white"
              }`}
            >
              Yalnızca Katılım Uygun
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#242B35]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">Sırala:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortField)}
              className="bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2.5 py-3 md:py-1.5 text-white text-xs outline-none"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <button
              onClick={() => setOrder((o) => (o === "asc" ? "desc" : "asc"))}
              className="flex items-center gap-1 bg-[#0B0E14] border border-[#242B35] hover:border-[#10B981]/40 rounded-lg px-2.5 py-1.5 text-xs text-gray-400 hover:text-white transition"
            >
              {order === "asc" ? <ArrowUp className="w-3.5 h-3.5" /> : <ArrowDown className="w-3.5 h-3.5" />}
              {order === "asc" ? "Artan" : "Azalan"}
            </button>
          </div>

          <div className="flex items-center gap-2">
            {activeFilterCount > 0 && (
              <button
                onClick={() => setFilters(EMPTY_FILTERS)}
                className="flex items-center gap-1 text-[11px] text-gray-500 hover:text-[#F43F5E] transition py-3 md:py-0 px-1"
              >
                <X className="w-3 h-3" /> Filtreleri Temizle ({activeFilterCount})
              </button>
            )}
            <button
              onClick={fetchScreener}
              className="bg-[#10B981] hover:bg-[#0da271] text-[#0B0E14] font-bold text-xs px-4 py-3 md:py-2 rounded-lg transition"
            >
              Uygula
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
          Taranıyor...
        </div>
      ) : items.length === 0 ? (
        <p className="text-center text-gray-500 text-xs py-16">Filtrelerinizle eşleşen hisse bulunamadı.</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-[#242B35]">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-[#151921] text-gray-500 text-left">
                <th className="px-3 py-2.5 font-semibold">Sembol</th>
                <th className="px-3 py-2.5 font-semibold hidden sm:table-cell">Sektör</th>
                <th className="px-3 py-2.5 font-semibold text-right">Fiyat</th>
                <th className="px-3 py-2.5 font-semibold text-right">Değişim</th>
                <th className="px-3 py-2.5 font-semibold text-right">F/K</th>
                <th className="px-3 py-2.5 font-semibold text-right">PD/DD</th>
                <th className="px-3 py-2.5 font-semibold text-right">ROE</th>
                <th className="px-3 py-2.5 font-semibold text-right hidden md:table-cell">Piotroski</th>
                <th className="px-3 py-2.5 font-semibold text-right hidden md:table-cell">Temettü</th>
                <th className="px-3 py-2.5 font-semibold hidden lg:table-cell">Katılım</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.symbol} className="border-t border-[#242B35] hover:bg-[#151921]/60">
                  <td className="px-3 py-2">
                    <Link href={`/hisse/${item.symbol}`} className="font-bold text-white hover:text-[#10B981]">
                      {item.symbol}
                    </Link>
                    <p className="text-[10px] text-gray-500 truncate max-w-[140px]">{item.company_name}</p>
                  </td>
                  <td className="px-3 py-2 text-gray-400 hidden sm:table-cell">{item.sector || "—"}</td>
                  <td className="px-3 py-2 text-right text-white tabular-nums">{item.current_price} TL</td>
                  <td className={`px-3 py-2 text-right font-semibold tabular-nums ${
                    marketTextClass(item.price_change_pct)
                  }`}>
                    {item.price_change_pct === null ? "—" : `${item.price_change_pct > 0 ? "+" : ""}${item.price_change_pct}%`}
                  </td>
                  <td className="px-3 py-2 text-right text-gray-300 tabular-nums">{fmt(item.pe_ratio)}</td>
                  <td className="px-3 py-2 text-right text-gray-300 tabular-nums">{fmt(item.pb_ratio)}</td>
                  <td className="px-3 py-2 text-right text-gray-300 tabular-nums">{fmt(item.roe, "%")}</td>
                  <td className="px-3 py-2 text-right text-gray-300 tabular-nums hidden md:table-cell">{fmt(item.piotroski_score, "/9")}</td>
                  <td className="px-3 py-2 text-right tabular-nums hidden md:table-cell" style={{ color: item.dividend_yield ? "#F59E0B" : undefined }}>{fmt(item.dividend_yield, "%")}</td>
                  <td className="px-3 py-2 hidden lg:table-cell">
                    <KatilimBadge isCompliant={item.is_katilim_compliant} status={item.katilim_status} size="sm" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
