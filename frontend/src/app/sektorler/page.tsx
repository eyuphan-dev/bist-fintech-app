"use client";

import React, { useEffect, useState } from "react";
import { Layers, RefreshCw, Info } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Sector {
  sector: string;
  stock_count: number;
  median_pe: number | null;
  median_pb: number | null;
  median_roe: number | null;
  median_dividend_yield: number | null;
  avg_change_pct: number | null;
  total_market_cap: number | null;
  katilim_compliant_count: number;
}

type SortKey = "stock_count" | "median_pe" | "median_pb" | "median_roe" | "median_dividend_yield" | "avg_change_pct";

const fmt = (v: number | null, suffix = "") =>
  v === null || v === undefined ? "—" : `${v.toLocaleString("tr-TR", { maximumFractionDigits: 2 })}${suffix}`;

function fmtCap(v: number | null): string {
  if (!v) return "—";
  if (v >= 1e12) return `${(v / 1e12).toLocaleString("tr-TR", { maximumFractionDigits: 2 })} trl`;
  if (v >= 1e9) return `${(v / 1e9).toLocaleString("tr-TR", { maximumFractionDigits: 1 })} mlr`;
  return `${(v / 1e6).toLocaleString("tr-TR", { maximumFractionDigits: 0 })} mn`;
}

export default function SectorsPage() {
  const { token, loading: authLoading, refreshTrigger } = useAuth();
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortKey>("stock_count");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/sectors`);
        if (res.ok && !cancelled) setSectors(await res.json());
      } catch (err) {
        console.error("Sektör verisi alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [refreshTrigger]);

  if (authLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <RefreshCw className="w-10 h-10 text-[#10B981] animate-spin mb-4" />
        <p className="text-gray-400 font-medium">Yükleniyor...</p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5 text-center">
          <p className="text-xs text-gray-400">Sektör analizini görmek için giriş yapmalısınız.</p>
        </div>
      </div>
    );
  }

  // null değerler her zaman en sona; aksi halde "veri yok" olanlar en ucuz gibi görünürdü.
  const sorted = [...sectors].sort((a, b) => {
    const av = a[sortBy], bv = b[sortBy];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    // F/K ve PD/DD'de düşük olan daha "ucuz" sayıldığı için artan sıralanır.
    const ascending = sortBy === "median_pe" || sortBy === "median_pb";
    return ascending ? av - bv : bv - av;
  });

  const COLUMNS: { key: SortKey; label: string; render: (s: Sector) => string; hint: string }[] = [
    { key: "stock_count", label: "Hisse", render: (s) => String(s.stock_count), hint: "Sektördeki hisse sayısı" },
    { key: "median_pe", label: "F/K", render: (s) => fmt(s.median_pe), hint: "Medyan Fiyat/Kazanç — düşüğü genelde daha ucuz" },
    { key: "median_pb", label: "PD/DD", render: (s) => fmt(s.median_pb), hint: "Medyan Piyasa Değeri/Defter Değeri" },
    { key: "median_roe", label: "ROE", render: (s) => fmt(s.median_roe, "%"), hint: "Medyan özkaynak kârlılığı" },
    { key: "median_dividend_yield", label: "Temettü", render: (s) => fmt(s.median_dividend_yield, "%"), hint: "Medyan temettü verimi" },
    { key: "avg_change_pct", label: "Bugün", render: (s) => fmt(s.avg_change_pct, "%"), hint: "Sektörün bugünkü ortalama değişimi" },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Layers className="w-5 h-5 text-[#F59E0B]" /> Sektör Analizi
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Hangi sektör ucuz, hangisi pahalı? Sektör bazlı değerleme oranları ve
          bugünkü performans. Başlıklara tıklayarak sıralayabilirsiniz.
        </p>
      </div>

      {loading ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-8 text-center">
          <p className="text-xs text-gray-500">Yükleniyor...</p>
        </div>
      ) : (
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[600px]">
              <thead>
                <tr className="border-b border-[#242B35] text-gray-400">
                  <th className="pb-3 pr-3 font-semibold">Sektör</th>
                  {COLUMNS.map((c) => (
                    <th key={c.key} className="pb-3 px-3 font-semibold text-right">
                      <button
                        onClick={() => setSortBy(c.key)}
                        title={c.hint}
                        type="button"
                        className={`transition ${sortBy === c.key ? "text-[#10B981]" : "hover:text-white"}`}
                      >
                        {c.label}
                      </button>
                    </th>
                  ))}
                  <th className="pb-3 pl-3 font-semibold text-right hidden md:table-cell">Piyasa Değeri</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((s) => (
                  <tr key={s.sector} className="border-b border-[#242B35]/50">
                    <td className="py-2.5 pr-3">
                      <span className="font-bold text-white">{s.sector}</span>
                      {s.katilim_compliant_count > 0 && (
                        <span className="block text-[10px] text-[#10B981]">
                          {s.katilim_compliant_count}/{s.stock_count} katılım uygun
                        </span>
                      )}
                    </td>
                    {COLUMNS.map((c) => {
                      const isChange = c.key === "avg_change_pct";
                      const v = s[c.key];
                      const color = isChange && v !== null
                        ? (v as number) >= 0 ? "#10B981" : "#F43F5E"
                        : undefined;
                      return (
                        <td
                          key={c.key}
                          className="py-2.5 px-3 text-right tabular-nums font-semibold text-gray-300"
                          style={color ? { color } : undefined}
                        >
                          {isChange && v !== null && (v as number) >= 0 ? "+" : ""}
                          {c.render(s)}
                        </td>
                      );
                    })}
                    <td className="py-2.5 pl-3 text-right tabular-nums text-gray-400 hidden md:table-cell">
                      {fmtCap(s.total_market_cap)} TL
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-[10px] text-gray-600 mt-4 border-t border-[#242B35] pt-3 flex items-start gap-1.5">
            <Info className="w-3 h-3 shrink-0 mt-0.5" />
            <span>
              Oranlarda <strong>ortalama değil medyan</strong> kullanılır: sektör başına
              3-5 hisse olduğu için tek bir aykırı değer ortalamayı tamamen bozar
              (örneğin F/K 4-5-6-200 olan bir sektörde ortalama 54, medyan 5,5 çıkar).
              Zarar eden şirketlerin F/K&apos;sı hesaba katılmaz. Yatırım tavsiyesi değildir.
            </span>
          </p>
        </div>
      )}
    </div>
  );
}
