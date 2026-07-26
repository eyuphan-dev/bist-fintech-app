"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Activity, Award, ArrowLeftRight, TrendingUp, TrendingDown, CheckCircle2, RefreshCw } from "lucide-react";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

interface BotStats {
  total_trades: number;
  win_rate: number;
  total_return_pct: number;
  balance: number;
  portfolio_value: number;
}

interface BotLog {
  id: number;
  symbol: string;
  action_type: "AL" | "SAT";
  price: number;
  quantity: number;
  reason_text: string;
  created_at: string;
}

interface PerformancePoint {
  date: string;
  value: number;
}

/** Quant AI Bot Kontrol Paneli: Bot vs BİST 100 performansı, Win Rate ve canlı işlem akışı. */
export default function QuantBotDashboard() {
  const [stats, setStats] = useState<BotStats | null>(null);
  const [logs, setLogs] = useState<BotLog[]>([]);
  const [perf, setPerf] = useState<{ bot: PerformancePoint[]; bist100: PerformancePoint[] }>({ bot: [], bist100: [] });
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    try {
      const [statsRes, logsRes, perfRes] = await Promise.all([
        fetch(`${API_BASE}/bot/stats`),
        fetch(`${API_BASE}/bot/logs`),
        fetch(`${API_BASE}/bot/performance`),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (logsRes.ok) setLogs(await logsRes.json());
      if (perfRes.ok) setPerf(await perfRes.json());
    } catch (err) {
      console.error("Quant Bot verisi alınamadı:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 20000);
    return () => clearInterval(interval);
  }, []);

  const dates = perf.bot.map((d) => new Date(d.date).toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" }));
  const series = [
    { name: "Quant AI Bot", data: perf.bot.map((d) => d.value) },
    { name: "BİST 100 (Ort.)", data: perf.bist100.map((d) => d.value) },
  ];
  const chartOptions: ApexCharts.ApexOptions = {
    chart: { type: "area", background: "transparent", toolbar: { show: false }, zoom: { enabled: false } },
    theme: { mode: "dark" },
    colors: ["#10B981", "#F59E0B"],
    dataLabels: { enabled: false },
    stroke: { curve: "smooth", width: 2.5 },
    fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.3, opacityTo: 0.02, stops: [0, 95, 100] } },
    grid: { borderColor: "#242B35", strokeDashArray: 4, xaxis: { lines: { show: false } } },
    xaxis: { categories: dates, axisBorder: { show: false }, axisTicks: { show: false }, labels: { style: { colors: "#6b7280", fontSize: "11px" } } },
    yaxis: { labels: { style: { colors: "#6b7280", fontSize: "11px" }, formatter: (v) => v.toLocaleString("tr-TR", { maximumFractionDigits: 0 }) + " TL" } },
    tooltip: { theme: "dark", shared: true, y: { formatter: (v) => v.toLocaleString("tr-TR", { minimumFractionDigits: 2 }) + " TL" } },
    legend: { position: "top", horizontalAlign: "right", labels: { colors: "#d1d5db" } },
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#F59E0B]" />
        Quant Bot verileri yükleniyor...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {stats && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex items-center justify-between">
            <div>
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-wide">Kasa Değeri</span>
              <h4 className="text-lg font-bold text-white tabular-nums mt-1">{stats.portfolio_value.toLocaleString("tr-TR")} TL</h4>
              <p className={`text-[11px] font-semibold mt-0.5 flex items-center gap-1 ${stats.total_return_pct >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"}`}>
                {stats.total_return_pct >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {stats.total_return_pct >= 0 ? "+" : ""}{stats.total_return_pct}% Toplam
              </p>
            </div>
            <div className="w-9 h-9 bg-[#10B981]/10 rounded-lg flex items-center justify-center">
              <Activity className="w-4.5 h-4.5 text-[#10B981]" />
            </div>
          </div>

          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex items-center justify-between">
            <div>
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-wide">İşlem Sayısı</span>
              <h4 className="text-lg font-bold text-white tabular-nums mt-1">{stats.total_trades}</h4>
              <p className="text-[11px] text-gray-500 mt-0.5">Toplam Al / Sat</p>
            </div>
            <div className="w-9 h-9 bg-[#F59E0B]/10 rounded-lg flex items-center justify-center">
              <ArrowLeftRight className="w-4.5 h-4.5 text-[#F59E0B]" />
            </div>
          </div>

          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex items-center justify-between">
            <div>
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-wide">Win Rate</span>
              <h4 className="text-lg font-bold text-white tabular-nums mt-1">%{stats.win_rate}</h4>
              <p className="text-[11px] text-gray-500 mt-0.5">Kârlı Pozisyon Oranı</p>
            </div>
            <div className="w-9 h-9 bg-[#F59E0B]/10 rounded-lg flex items-center justify-center">
              <Award className="w-4.5 h-4.5 text-[#F59E0B]" />
            </div>
          </div>
        </div>
      )}

      <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
        <h3 className="text-sm font-bold text-white uppercase tracking-wide mb-3">Bot vs BİST 100 Performans Karşılaştırması</h3>
        <Chart options={chartOptions} series={series} type="area" height={280} />
      </div>

      <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
        <h3 className="text-sm font-bold text-white uppercase tracking-wide mb-4">Canlı İşlem Akışı</h3>
        {logs.length === 0 ? (
          <p className="text-center py-6 text-gray-500 text-xs">Bot henüz işlem yapmadı. BİST seansı saatlerinde işlem yapacaktır.</p>
        ) : (
          <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
            {logs.map((log) => (
              <div key={log.id} className="p-3.5 bg-[#0B0E14] border border-[#242B35] rounded-xl space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white">{log.symbol}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${log.action_type === "AL" ? "bg-[#10B981]/10 text-[#10B981]" : "bg-[#F43F5E]/10 text-[#F43F5E]"}`}>
                      {log.action_type}
                    </span>
                  </div>
                  <span className="text-[10px] text-gray-500 tabular-nums">
                    {new Date(log.created_at).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
                <p className="text-gray-400 font-medium tabular-nums">
                  {log.quantity} adet {log.symbol} — {log.price} TL
                </p>
                <div className="pt-1.5 border-t border-[#242B35] flex items-start gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0 mt-0.5" />
                  <p className="text-[10px] text-gray-400 italic">
                    <span className="font-semibold text-gray-300 not-italic">Neden:</span> {log.reason_text}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
