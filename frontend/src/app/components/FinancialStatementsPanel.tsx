"use client";

import React, { useEffect, useState } from "react";
import { FileSpreadsheet, TrendingUp, TrendingDown } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface Period {
  period_end: string;
  period_label: string;
  revenue: number | null;
  gross_profit: number | null;
  operating_income: number | null;
  ebitda: number | null;
  net_income: number | null;
  total_assets: number | null;
  total_equity: number | null;
  total_debt: number | null;
  operating_cashflow: number | null;
  revenue_yoy_pct: number | null;
  net_income_yoy_pct: number | null;
  net_margin_pct: number | null;
}

interface Data {
  symbol: string;
  company_name: string;
  periods: Period[];
}

/** Büyük TL tutarlarını okunur kısaltır: 1.234.000.000 -> "1,23 mlr". */
function fmtTL(v: number | null): string {
  if (v === null || v === undefined) return "—";
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toLocaleString("tr-TR", { maximumFractionDigits: 2 })} mlr`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toLocaleString("tr-TR", { maximumFractionDigits: 1 })} mn`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toLocaleString("tr-TR", { maximumFractionDigits: 0 })} bin`;
  return `${sign}${abs.toLocaleString("tr-TR", { maximumFractionDigits: 0 })}`;
}

const ROWS: { key: keyof Period; label: string; group: string }[] = [
  { key: "revenue", label: "Hasılat", group: "Gelir Tablosu" },
  { key: "gross_profit", label: "Brüt Kâr", group: "Gelir Tablosu" },
  { key: "operating_income", label: "Faaliyet Kârı", group: "Gelir Tablosu" },
  { key: "ebitda", label: "FAVÖK", group: "Gelir Tablosu" },
  { key: "net_income", label: "Net Kâr", group: "Gelir Tablosu" },
  { key: "total_assets", label: "Toplam Varlık", group: "Bilanço" },
  { key: "total_equity", label: "Özkaynak", group: "Bilanço" },
  { key: "total_debt", label: "Toplam Borç", group: "Bilanço" },
  { key: "operating_cashflow", label: "Faaliyet Nakit Akışı", group: "Nakit Akışı" },
];

/**
 * Çeyreklik finansal tablolar — ücretli platformların paket içinde sunduğu
 * özelliğin karşılığı. Veri gece işiyle doldurulur (financials.py).
 */
export default function FinancialStatementsPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/financials`);
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Finansal tablolar alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [symbol]);

  if (loading) return null;

  if (!data || data.periods.length === 0) {
    return (
      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <FileSpreadsheet className="w-4 h-4 text-[#F59E0B]" />
          <h4 className="text-xs font-bold text-white uppercase tracking-wide">Finansal Tablolar</h4>
        </div>
        <p className="text-[11px] text-gray-500">
          Bu hisse için çeyreklik finansal tablo verisi henüz çekilmedi. Gece
          çalışan tazeleme işiyle birkaç gün içinde dolacaktır.
        </p>
      </div>
    );
  }

  // En yeni dönem solda olsun diye sıralama zaten azalan geliyor.
  const periods = data.periods.slice(0, 6);
  const latest = periods[0];

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <FileSpreadsheet className="w-4 h-4 text-[#F59E0B]" />
        <h4 className="text-xs font-bold text-white uppercase tracking-wide">
          Çeyreklik Finansal Tablolar
        </h4>
      </div>

      {/* Son çeyreğin yıllık büyümesi — tek bakışta özet */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "Hasılat (yıllık)", value: latest.revenue_yoy_pct },
          { label: "Net Kâr (yıllık)", value: latest.net_income_yoy_pct },
          { label: "Net Marj", value: latest.net_margin_pct, plain: true },
        ].map((x) => {
          const positive = (x.value ?? 0) >= 0;
          const color = x.value === null ? "#8A99AD" : x.plain ? "#F8FAFC" : positive ? "#10B981" : "#F43F5E";
          return (
            <div key={x.label} className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-2.5">
              <p className="text-[9px] text-gray-500 uppercase font-bold">{x.label}</p>
              <p className="text-sm font-bold tabular-nums mt-0.5 flex items-center gap-1" style={{ color }}>
                {x.value === null ? "—" : (
                  <>
                    {!x.plain && (positive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />)}
                    {!x.plain && positive ? "+" : ""}%{x.value.toFixed(1)}
                  </>
                )}
              </p>
            </div>
          );
        })}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-[11px] min-w-[520px]">
          <thead>
            <tr className="border-b border-[#242B35] text-gray-500">
              <th className="pb-2 pr-3 font-semibold sticky left-0 bg-[#151921]">Kalem</th>
              {periods.map((p) => (
                <th key={p.period_end} className="pb-2 px-2 font-semibold text-right whitespace-nowrap">
                  {p.period_label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row, i) => {
              const prevGroup = i > 0 ? ROWS[i - 1].group : null;
              const showGroup = row.group !== prevGroup;
              return (
                <React.Fragment key={row.key as string}>
                  {showGroup && (
                    <tr>
                      <td
                        colSpan={periods.length + 1}
                        className="pt-3 pb-1 text-[9px] font-bold text-[#F59E0B] uppercase tracking-wider"
                      >
                        {row.group}
                      </td>
                    </tr>
                  )}
                  <tr className="border-b border-[#242B35]/40">
                    <td className="py-1.5 pr-3 text-gray-300 sticky left-0 bg-[#151921] whitespace-nowrap">
                      {row.label}
                    </td>
                    {periods.map((p) => (
                      <td key={p.period_end} className="py-1.5 px-2 text-right tabular-nums text-gray-200 whitespace-nowrap">
                        {fmtTL(p[row.key] as number | null)}
                      </td>
                    ))}
                  </tr>
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="text-[10px] text-gray-600 border-t border-[#242B35] pt-2.5">
        Tutarlar TL. Büyüme oranları bir önceki YILIN AYNI çeyreğine göredir —
        çeyrekler mevsimsellik taşıdığı için ardışık çeyrek karşılaştırması
        yanıltıcı olurdu. Kaynak: Yahoo Finance; resmi tablolar için KAP&apos;a bakın.
      </p>
    </div>
  );
}
