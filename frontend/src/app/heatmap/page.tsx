"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { RefreshCw, LayoutGrid, Table2 } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface Stock {
  id: number;
  symbol: string;
  company_name: string;
  is_active: boolean;
  sector: string | null;
  current_price: number;
  price_change_pct: number | null;
  is_katilim_compliant: boolean;
  purification_rate: number;
}

// Diğişim yüzdesi (polarite) için doğrulanmış diverging renk çifti — validate_palette.js
// script'i ile CVD/kontrast kontrollerinin tümünden geçti (bkz. dataviz skill raporu):
// negatif kutup mevcut uygulamanın kırmızısı (#F43F5E), pozitif kutup ise yeşille
// karıştırılabilecek klasik yeşilin aksine ayırt edilebilir bir camgöbeği (#0D9488).
const NEGATIVE_HEX = "#F43F5E";
const NEUTRAL_HEX = "#5B6472";
const POSITIVE_HEX = "#0D9488";
const MIN_HEAT_CLAMP_PCT = 0.5; // piyasa çok durgunken bile skala anlamlı kalsın diye taban değer

function hexToRgb(hex: string): [number, number, number] {
  const v = hex.replace("#", "");
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
}

function interpolateHex(a: string, b: string, t: number): string {
  const [ar, ag, ab] = hexToRgb(a);
  const [br, bg, bb] = hexToRgb(b);
  const r = Math.round(ar + (br - ar) * t);
  const g = Math.round(ag + (bg - ag) * t);
  const bch = Math.round(ab + (bb - ab) * t);
  return `rgb(${r}, ${g}, ${bch})`;
}

function getHeatColor(pct: number, clampPct: number): string {
  const clamped = Math.max(-clampPct, Math.min(clampPct, pct));
  if (clamped >= 0) return interpolateHex(NEUTRAL_HEX, POSITIVE_HEX, clamped / clampPct);
  return interpolateHex(NEUTRAL_HEX, NEGATIVE_HEX, -clamped / clampPct);
}

const UNCATEGORIZED = "Diğer";

export default function HeatmapPage() {
  const { refreshTrigger } = useAuth();
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"heatmap" | "table">("heatmap");

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

  // Sembol -> yüzde değişim eşleşmesi; fill.colors callback'i içinde y (kutu boyutu,
  // her zaman pozitif) yerine gerçek işaretli değere buradan erişiyoruz. Backend, bir
  // kurumsal işlem (bölünme/bedelsiz) sonrası yanlış sıçrama göstermemek için bilinçli
  // olarak null döndürebiliyor (bkz. EXTREME_CHANGE_GUARD_PCT) — null'ı 0 sanıp "hiç
  // değişmemiş/yeşil" göstermek yanlış olur, bu yüzden Map açıkça null'ı da taşır.
  const pctBySymbol = useMemo(() => {
    const map = new Map<string, number | null>();
    stocks.forEach((s) => map.set(s.symbol, s.price_change_pct));
    return map;
  }, [stocks]);

  // Renk skalası günün gerçek hareket aralığına göre kalibre edilir: sabit ±3% gibi bir
  // eşik, hareketlerin çoğu ±1%'in altında kaldığında neredeyse tüm kutuları aynı gri
  // tonda gösterip skalayı anlamsızlaştırıyordu. En büyük hareketi doygunluk noktası yapmak
  // renk farkını her zaman görünür kılar. null (karşılaştırılamayan) hisseler hariç tutulur.
  const heatClampPct = useMemo(() => {
    const maxAbs = stocks.reduce((m, s) => (s.price_change_pct === null ? m : Math.max(m, Math.abs(s.price_change_pct))), 0);
    return Math.max(MIN_HEAT_CLAMP_PCT, maxAbs);
  }, [stocks]);

  const sectorGroups = useMemo(() => {
    const groups = new Map<string, Stock[]>();
    stocks.forEach((s) => {
      const key = s.sector || UNCATEGORIZED;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(s);
    });
    return Array.from(groups.entries()).sort((a, b) => b[1].length - a[1].length);
  }, [stocks]);

  const series = useMemo(
    () =>
      sectorGroups.map(([sector, items]) => ({
        name: sector,
        data: items.map((s) => ({
          x: s.symbol,
          // Kutu boyutu: hareketin büyüklüğü (mutlak değişim), asla sıfır olmasın diye taban değer eklendi.
          // Karşılaştırılamayan (null) hisseler en küçük/nötr kutu olarak gösterilir.
          y: Math.round((0.3 + Math.abs(s.price_change_pct ?? 0)) * 100) / 100,
        })),
      })),
    [sectorGroups]
  );

  const chartOptions = useMemo(
    () => ({
      chart: {
        type: "treemap" as const,
        toolbar: { show: false },
        background: "transparent",
        foreColor: "#9CA3AF",
      },
      legend: { show: false },
      dataLabels: {
        enabled: true,
        style: { fontSize: "11px", fontWeight: 700 },
        formatter: (text: string) => {
          const pct = pctBySymbol.get(text);
          if (pct === null || pct === undefined) return [text, "—"];
          return [text, `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`];
        },
      },
      plotOptions: {
        treemap: {
          distributed: false,
          enableShades: false,
        },
      },
      // Kutu başına özel renk vermenin yolu fill.colors'a bir fonksiyon vermek: kutunun
      // y değeri (boyut = hareketin büyüklüğü) yerine gerçek işaretli yüzdeyi
      // (pctBySymbol'den) okuyup oradan diverging rengi hesaplıyoruz.
      fill: {
        // ApexCharts'ın kendi tipleri fill.colors'ı string[] olarak bildirse de, kütüphane
        // çalışma zamanında treemap için bir renk fonksiyonunu da kabul ediyor (resmi örnek
        // kullanımı) — bu yüzden tip uyuşmazlığını burada bilinçli olarak bastırıyoruz.
        colors: [
          ({ seriesIndex, dataPointIndex }: { seriesIndex: number; dataPointIndex: number }) => {
            const point = series[seriesIndex]?.data[dataPointIndex];
            if (!point) return NEUTRAL_HEX;
            const pct = pctBySymbol.get(point.x);
            if (pct === null || pct === undefined) return NEUTRAL_HEX;
            return getHeatColor(pct, heatClampPct);
          },
        ] as unknown as string[],
      },
      stroke: { width: 2, colors: ["#0B0E14"] },
      tooltip: {
        theme: "dark" as const,
        custom: ({ seriesIndex, dataPointIndex }: { seriesIndex: number; dataPointIndex: number }) => {
          const point = series[seriesIndex]?.data[dataPointIndex];
          if (!point) return "";
          const pct = pctBySymbol.get(point.x);
          const isUnavailable = pct === null || pct === undefined;
          const color = isUnavailable ? NEUTRAL_HEX : getHeatColor(pct, heatClampPct);
          const label = isUnavailable
            ? "Kurumsal işlem nedeniyle karşılaştırılamıyor"
            : `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;
          return `<div style="background:#151921;border:1px solid #242B35;border-radius:8px;padding:8px 10px;font-size:12px;color:#fff">
            <div style="font-weight:700">${point.x}</div>
            <div style="color:${color};font-weight:700">${label}</div>
          </div>`;
        },
      },
    }),
    [series, pctBySymbol, heatClampPct]
  );

  const sortedTableStocks = useMemo(
    () => [...stocks].sort((a, b) => (a.sector || UNCATEGORIZED).localeCompare(b.sector || UNCATEGORIZED) || a.symbol.localeCompare(b.symbol)),
    [stocks]
  );

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-white">Sektörel Isı Haritası</h1>
          <p className="text-xs text-gray-500 mt-1">
            BİST hisselerini sektöre göre gruplayıp günlük değişime göre renklendirir. Kutu boyutu hareketin
            büyüklüğünü, renk yönünü (kazanç/kayıp) gösterir.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setView("heatmap")}
            className={`flex items-center gap-1.5 px-3.5 py-3 md:py-2 rounded-lg text-xs font-semibold border transition ${
              view === "heatmap"
                ? "bg-[#4A87C7]/10 border-[#4A87C7]/30 text-[#4A87C7]"
                : "bg-[#151921] border-[#242B35] text-gray-400 hover:text-white"
            }`}
          >
            <LayoutGrid className="w-3.5 h-3.5" /> Harita
          </button>
          <button
            onClick={() => setView("table")}
            className={`flex items-center gap-1.5 px-3.5 py-3 md:py-2 rounded-lg text-xs font-semibold border transition ${
              view === "table"
                ? "bg-[#4A87C7]/10 border-[#4A87C7]/30 text-[#4A87C7]"
                : "bg-[#151921] border-[#242B35] text-gray-400 hover:text-white"
            }`}
          >
            <Table2 className="w-3.5 h-3.5" /> Tablo
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#4A87C7]" />
          Hisseler yükleniyor...
        </div>
      ) : stocks.length === 0 ? (
        <p className="text-center text-gray-500 text-xs py-10">Gösterilecek hisse bulunamadı.</p>
      ) : view === "heatmap" ? (
        <div className="space-y-3">
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
            <Chart options={chartOptions} series={series} type="treemap" height={520} />
          </div>

          {/* Diverging renk skalası — kategorik değil, kutuplu (kazanç/kayıp) bir skala
              olduğu için klasik seri legend'ı yerine gradyan bar + uç etiketleri kullanılıyor. */}
          <div className="flex items-center gap-3 text-[10px] text-gray-500 px-1">
            <span>%-{heatClampPct.toFixed(1)} ve altı</span>
            <div
              className="h-2 flex-1 rounded-full"
              style={{
                background: `linear-gradient(to right, ${NEGATIVE_HEX}, ${NEUTRAL_HEX}, ${POSITIVE_HEX})`,
              }}
            />
            <span>%+{heatClampPct.toFixed(1)} ve üstü</span>
          </div>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-[#242B35]">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-[#151921] text-gray-500 text-left">
                <th className="px-3 py-2.5 font-semibold">Sektör</th>
                <th className="px-3 py-2.5 font-semibold">Sembol</th>
                <th className="px-3 py-2.5 font-semibold">Şirket</th>
                <th className="px-3 py-2.5 font-semibold text-right">Fiyat</th>
                <th className="px-3 py-2.5 font-semibold text-right">Değişim</th>
              </tr>
            </thead>
            <tbody>
              {sortedTableStocks.map((s) => (
                <tr key={s.symbol} className="border-t border-[#242B35] hover:bg-[#151921]/60">
                  <td className="px-3 py-2 text-gray-400">{s.sector || UNCATEGORIZED}</td>
                  <td className="px-3 py-2">
                    <Link href={`/hisse/${s.symbol}`} className="font-bold text-white hover:text-[#4A87C7]">
                      {s.symbol}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-gray-400 truncate max-w-[220px]">{s.company_name}</td>
                  <td className="px-3 py-2 text-right text-white tabular-nums">{s.current_price} TL</td>
                  {s.price_change_pct !== null ? (
                    <td
                      className={`px-3 py-2 text-right font-semibold tabular-nums ${
                        s.price_change_pct >= 0 ? "text-[#0D9488]" : "text-[#F43F5E]"
                      }`}
                    >
                      {s.price_change_pct > 0 ? "+" : ""}
                      {s.price_change_pct}%
                    </td>
                  ) : (
                    <td
                      title="Kurumsal işlem (bölünme/bedelsiz sermaye artışı) nedeniyle günlük değişim şu an güvenilir hesaplanamıyor."
                      className="px-3 py-2 text-right font-semibold tabular-nums text-gray-500"
                    >
                      —
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
