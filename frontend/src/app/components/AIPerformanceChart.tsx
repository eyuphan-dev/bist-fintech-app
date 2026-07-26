"use client";

import React from "react";
import dynamic from "next/dynamic";

// Dynamically import react-apexcharts to avoid SSR errors in Next.js
const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface PerformancePoint {
  date: string;
  value: number;
}

interface AIPerformanceChartProps {
  botData: PerformancePoint[];
  bist100Data: PerformancePoint[];
}

export default function AIPerformanceChart({ botData, bist100Data }: AIPerformanceChartProps) {
  // Extract dates and values
  const dates = botData.map((d) => {
    // Format YYYY-MM-DD to DD.MM
    const dateObj = new Date(d.date);
    return dateObj.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit" });
  });
  
  const botValues = botData.map((d) => d.value);
  const bistValues = bist100Data.map((d) => d.value);

  const series = [
    {
      name: "Yapay Zeka Trader (Sim)",
      data: botValues,
    },
    {
      name: "BİST 100 Endeksi (Ort.)",
      data: bistValues,
    },
  ];

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: "area",
      background: "transparent",
      toolbar: { show: false },
      zoom: { enabled: false },
      fontFamily: "var(--font-outfit), sans-serif",
    },
    theme: {
      mode: "dark",
    },
    colors: ["#10b981", "#3b82f6"],
    dataLabels: { enabled: false },
    stroke: {
      curve: "smooth",
      width: 2.5,
    },
    fill: {
      type: "gradient",
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.35,
        opacityTo: 0.02,
        stops: [0, 95, 100],
      },
    },
    grid: {
      borderColor: "rgba(55, 65, 81, 0.15)",
      strokeDashArray: 4,
      xaxis: { lines: { show: false } },
      yaxis: { lines: { show: true } },
      padding: { top: 10, right: 10, bottom: 0, left: 10 },
    },
    xaxis: {
      categories: dates,
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: {
        style: { colors: "#6b7280", fontSize: "11px" },
      },
    },
    yaxis: {
      labels: {
        style: { colors: "#6b7280", fontSize: "11px" },
        formatter: (val) => {
          return val.toLocaleString("tr-TR", { maximumFractionDigits: 0 }) + " TL";
        },
      },
    },
    tooltip: {
      theme: "dark",
      shared: true,
      intersect: false,
      y: {
        formatter: (val) => {
          return val.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " TL";
        },
      },
    },
    legend: {
      position: "top",
      horizontalAlign: "right",
      fontSize: "12px",
      labels: { colors: "#d1d5db" },
      markers: {
        size: 6,
      },
    },
  };

  return (
    <div className="w-full bg-slate-900/40 p-4 rounded-xl border border-gray-800/60">
      <Chart options={options} series={series} type="area" height={280} />
    </div>
  );
}
