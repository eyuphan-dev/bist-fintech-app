"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { TrendingUp } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface PerformancePoint {
  date: string;
  total_portfolio_value: number;
}

/**
 * Kullanıcının kendi portföy değerinin zaman içindeki seyri.
 *
 * Veri, scheduler'ın hafta içi her akşam aldığı gün sonu anlık görüntülerinden
 * gelir; bu nedenle yeni bir hesapta grafik ancak birkaç gün sonra anlamlı olur.
 * En az 2 nokta yoksa çizgi grafik yanıltıcı olacağından bileşen gizlenir.
 */
export default function PortfolioPerformanceChart({ refreshKey }: { refreshKey?: number }) {
  const { token } = useAuth();
  const [points, setPoints] = useState<PerformancePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/portfolio/performance`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && !cancelled) setPoints(await res.json());
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

  if (loading || points.length < 2) return null;

  const first = points[0].total_portfolio_value;
  const last = points[points.length - 1].total_portfolio_value;
  const changePct = first > 0 ? ((last - first) / first) * 100 : 0;
  const positive = changePct >= 0;
  const lineColor = positive ? "#10B981" : "#F43F5E";

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-white tracking-wide uppercase flex items-center gap-1.5">
          <TrendingUp className="w-4 h-4 text-[#10B981]" /> Portföy Değer Geçmişi
        </h3>
        <span
          className="text-xs font-bold tabular-nums"
          style={{ color: lineColor }}
        >
          {positive ? "+" : ""}
          {changePct.toFixed(2)}%
        </span>
      </div>

      <Chart
        type="area"
        height={220}
        series={[
          {
            name: "Portföy Değeri",
            data: points.map((p) => ({ x: p.date, y: Number(p.total_portfolio_value.toFixed(2)) })),
          },
        ]}
        options={{
          chart: {
            toolbar: { show: false },
            zoom: { enabled: false },
            background: "transparent",
            fontFamily: "inherit",
          },
          theme: { mode: "dark" },
          colors: [lineColor],
          dataLabels: { enabled: false },
          stroke: { curve: "smooth", width: 2 },
          fill: {
            type: "gradient",
            gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0, stops: [0, 100] },
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
              formatter: (v: number) => `${Math.round(v).toLocaleString("tr-TR")}`,
            },
          },
          tooltip: {
            theme: "dark",
            x: { format: "dd MMM yyyy" },
            y: { formatter: (v: number) => `${v.toLocaleString("tr-TR")} TL` },
          },
        }}
      />

      <p className="text-[10px] text-gray-600 mt-2">
        Gün sonu portföy değerleriniz (nakit + hisse) hafta içi her akşam kaydedilir.
      </p>
    </div>
  );
}
