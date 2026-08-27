"use client";

import React, { useEffect, useState } from "react";
import { CalendarClock, Info } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface MonthData {
  month: number;
  month_name: string;
  years_observed: number;
  avg_return_pct: number;
  positive_year_ratio: number;
}

interface SeasonalityData {
  available: boolean;
  symbol: string;
  months: MonthData[];
  note: string;
}

/**
 * Aylık mevsimsellik — hisse tarihsel olarak hangi ayda ortalama nasıl
 * hareket etmiş. Tamamen kendi günlük fiyat geçmişimizden hesaplanır.
 *
 * ÖNEMLİ: bu bir tahmin aracı değildir, `note` alanındaki uyarı her zaman
 * gösterilir. Az sayıda gözleme (genelde 3-5 yıl) dayanır.
 */
export default function SeasonalityPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<SeasonalityData | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/seasonality`);
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Mevsimsellik verisi alınamadı:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [symbol]);

  if (!data || !data.available || data.months.length === 0) return null;

  const maxAbs = Math.max(...data.months.map((m) => Math.abs(m.avg_return_pct)), 0.0001);

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3 space-y-3">
      <div className="flex items-center gap-2">
        <CalendarClock className="w-3.5 h-3.5 text-[#F59E0B]" />
        <p className="text-[9px] text-gray-500 uppercase font-bold">Aylık Mevsimsellik</p>
      </div>

      <div className="grid grid-cols-6 gap-1.5">
        {data.months.map((m) => {
          const positive = m.avg_return_pct >= 0;
          const barHeight = Math.max(8, (Math.abs(m.avg_return_pct) / maxAbs) * 32);
          return (
            <div key={m.month} className="flex flex-col items-center gap-1" title={
              `${m.month_name}: ${m.years_observed} yılın %${Math.round(m.positive_year_ratio * 100)}'inde yükseldi`
            }>
              <div className="h-8 flex items-end">
                <div
                  className="w-3 rounded-sm"
                  style={{ height: `${barHeight}px`, backgroundColor: positive ? "#10B981" : "#F43F5E" }}
                />
              </div>
              <span className="text-[8px] text-gray-500">{m.month_name.slice(0, 3)}</span>
              <span
                className="text-[8px] font-semibold tabular-nums"
                style={{ color: positive ? "#10B981" : "#F43F5E" }}
              >
                {positive ? "+" : ""}{m.avg_return_pct.toFixed(1)}%
              </span>
            </div>
          );
        })}
      </div>

      <p className="text-[9px] text-gray-600 flex items-start gap-1.5">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        {data.note}
      </p>
    </div>
  );
}
