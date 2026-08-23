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

/**
 * Hasılat ve net kâr trendi.
 *
 * Tablo sayıları veriyor ama yönü vermiyor: 6 çeyreklik rakama bakıp "büyüyor
 * mu, daralıyor mu" sorusunu cevaplamak zor. Çubuklar hasılatı, çizgi net kârı
 * gösterir. İkisinin ayrışması (hasılat artarken kâr düşmesi) marj sorununun
 * en hızlı okunan işaretidir.
 */
function TrendGrafigi({ periods }: { periods: Period[] }) {
  // Kronolojik: en eski solda. Veri en yeniden geliyor.
  const seri = [...periods].reverse().filter((p) => p.revenue !== null || p.net_income !== null);
  if (seri.length < 2) return null;

  const gelirler = seri.map((p) => p.revenue ?? 0);
  const karlar = seri.map((p) => p.net_income ?? 0);
  const maxGelir = Math.max(...gelirler.map(Math.abs), 1);
  // Net kâr negatif olabildiği için ekseni iki yöne açmak gerekir.
  const maxKar = Math.max(...karlar.map(Math.abs), 1);

  const W = 100, H = 44, bosluk = 2;
  const sutun = W / seri.length;
  const karY = (v: number) => H / 2 - (v / maxKar) * (H / 2 - 4);

  const cizgi = karlar
    .map((v, i) => `${i === 0 ? "M" : "L"} ${(i + 0.5) * sutun} ${karY(v)}`)
    .join(" ");

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <p className="text-[9px] text-gray-500 uppercase font-bold">Hasılat ve Net Kâr Trendi</p>
        <div className="flex items-center gap-2.5">
          <span className="flex items-center gap-1 text-[9px] text-gray-500">
            <span className="w-2 h-2 rounded-sm bg-[#2F6F5B]" /> Hasılat
          </span>
          <span className="flex items-center gap-1 text-[9px] text-gray-500">
            <span className="w-2.5 h-px bg-[#F59E0B]" /> Net Kâr
          </span>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-14" preserveAspectRatio="none">
        {/* Sıfır çizgisi: net kâr negatife düştüğünde nereye göre okunacağı belli olsun. */}
        <line x1="0" y1={H / 2} x2={W} y2={H / 2} stroke="#242B35" strokeWidth="0.4" />
        {gelirler.map((v, i) => {
          const y = (Math.abs(v) / maxGelir) * (H - 6);
          return (
            <rect
              key={i}
              x={i * sutun + bosluk / 2}
              y={H - y}
              width={sutun - bosluk}
              height={y}
              fill="#2F6F5B"
              rx="0.6"
            />
          );
        })}
        <path d={cizgi} fill="none" stroke="#F59E0B" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        {karlar.map((v, i) => (
          <circle key={i} cx={(i + 0.5) * sutun} cy={karY(v)} r="1.1" fill="#F59E0B" />
        ))}
      </svg>

      <div className="flex justify-between">
        {seri.map((p) => (
          <span key={p.period_end} className="text-[8px] text-gray-600 tabular-nums">
            {p.period_label}
          </span>
        ))}
      </div>
    </div>
  );
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

      <TrendGrafigi periods={periods} />

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
