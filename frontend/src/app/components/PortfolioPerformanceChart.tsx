"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { TrendingUp, Trophy } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface BenchmarkPoint {
  date: string;
  portfolio_value: number;
  portfolio_index: number;
  benchmark_index: number | null;
}

interface BenchmarkData {
  start_date: string | null;
  end_date: string | null;
  portfolio_return_pct: number | null;
  benchmark_return_pct: number | null;
  excess_return_pct: number | null;
  points: BenchmarkPoint[];
}

/**
 * Portföy değer geçmişi + BIST 100 kıyaslaması.
 *
 * Veri, scheduler'ın hafta içi her akşam aldığı gün sonu anlık görüntülerinden
 * gelir; bu nedenle yeni bir hesapta grafik ancak birkaç gün sonra anlamlı olur.
 * En az 2 nokta yoksa çizgi grafik yanıltıcı olacağından bileşen gizlenir.
 *
 * İki seri de ilk güne 100 verilerek normalize edilmiş halde gelir — böylece
 * puan cinsinden endeks ile TL cinsinden portföy aynı eksende kıyaslanabilir.
 */
export default function PortfolioPerformanceChart({ refreshKey }: { refreshKey?: number }) {
  const { token } = useAuth();
  const [data, setData] = useState<BenchmarkData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/portfolio/benchmark?days=180`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Portföy performans geçmişi alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, refreshKey]);

  if (loading || !data || data.points.length < 2) return null;

  const points = data.points;
  const changePct = data.portfolio_return_pct ?? 0;
  const positive = changePct >= 0;
  const lineColor = positive ? "#10B981" : "#F43F5E";

  const hasBenchmark = points.some((p) => p.benchmark_index !== null);
  const excess = data.excess_return_pct;

  const series: { name: string; data: { x: string; y: number | null }[] }[] = [
    {
      name: "Portföyüm",
      data: points.map((p) => ({ x: p.date, y: p.portfolio_index })),
    },
  ];
  if (hasBenchmark) {
    series.push({
      name: "BIST 100",
      data: points.map((p) => ({ x: p.date, y: p.benchmark_index })),
    });
  }

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
      <div className="flex items-center justify-between mb-3 gap-2">
        <h3 className="text-sm font-bold text-white tracking-wide uppercase flex items-center gap-1.5">
          <TrendingUp className="w-4 h-4 text-[#10B981]" /> Portföy Performansı
        </h3>
        <span className="text-xs font-bold tabular-nums" style={{ color: lineColor }}>
          {positive ? "+" : ""}
          {changePct.toFixed(2)}%
        </span>
      </div>

      {/* Endeksi yenip yenmediği tek bakışta görünsün */}
      {hasBenchmark && excess !== null && (
        <div
          className="flex items-center gap-2 rounded-lg px-3 py-2 mb-3 text-[11px] font-semibold"
          style={{
            backgroundColor: excess >= 0 ? "rgba(16,185,129,0.1)" : "rgba(244,63,94,0.1)",
            color: excess >= 0 ? "#10B981" : "#F43F5E",
          }}
        >
          <Trophy className="w-3.5 h-3.5 shrink-0" />
          {excess >= 0
            ? `BIST 100'ü %${excess.toFixed(2)} geride bıraktınız.`
            : `BIST 100'ün %${Math.abs(excess).toFixed(2)} gerisindesiniz.`}
          <span className="text-gray-500 font-normal ml-auto whitespace-nowrap">
            Endeks: {data.benchmark_return_pct?.toFixed(2)}%
          </span>
        </div>
      )}

      <Chart
        type="line"
        height={220}
        series={series}
        options={{
          chart: {
            toolbar: { show: false },
            zoom: { enabled: false },
            background: "transparent",
            fontFamily: "inherit",
          },
          theme: { mode: "dark" },
          // Portföy vurgulu (kalın), endeks referans (gri, ince kesikli)
          colors: [lineColor, "#8A99AD"],
          dataLabels: { enabled: false },
          stroke: { curve: "smooth", width: [2.5, 1.5], dashArray: [0, 4] },
          legend: {
            show: hasBenchmark,
            position: "top",
            horizontalAlign: "right",
            fontSize: "11px",
            labels: { colors: "#8A99AD" },
            markers: { size: 5 },
          },
          grid: { borderColor: "#242B35", strokeDashArray: 3 },
          xaxis: {
            type: "datetime",
            labels: { style: { colors: "#8A99AD", fontSize: "10px" } },
            axisBorder: { color: "#242B35" },
            axisTicks: { color: "#242B35" },
          },
          yaxis: {
            labels: {
              style: { colors: "#8A99AD", fontSize: "10px" },
              formatter: (v: number) => `${Math.round(v)}`,
            },
          },
          tooltip: {
            theme: "dark",
            shared: true,
            x: { format: "dd MMM yyyy" },
            y: { formatter: (v: number) => (v === null ? "—" : `${v.toFixed(2)}`) },
          },
        }}
      />

      <p className="text-[10px] text-gray-600 mt-2">
        Her iki seri de başlangıç günü 100 kabul edilerek ölçeklenmiştir; böylece puan
        cinsinden endeks ile TL cinsinden portföyünüz aynı grafikte kıyaslanabilir.
        Gün sonu değerleriniz hafta içi her akşam kaydedilir.
      </p>
    </div>
  );
}
