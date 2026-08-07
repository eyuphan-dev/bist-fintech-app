"use client";

import React, { useEffect, useRef } from "react";
import { createChart, ColorType, ISeriesApi, AreaSeries } from "lightweight-charts";

interface ChartDataPoint {
  price: number;
  recorded_at: string;
}

interface TradingViewChartProps {
  data: ChartDataPoint[];
  symbol: string;
}

export default function TradingViewChart({ data, symbol }: TradingViewChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    // Format data for lightweight-charts
    // time: string (YYYY-MM-DD) or number (timestamp)
    const formattedData = data.map((d) => {
      const dateObj = new Date(d.recorded_at);
      // We can use a timestamp in seconds to handle hourly/5m data, or just YYYY-MM-DD for daily
      // Let's use seconds timestamp to handle intra-day updates cleanly!
      return {
        // lightweight-charts zaman etiketlerini HER ZAMAN UTC olarak render eder
        // ve kütüphanenin saat dilimi ayarı yoktur. Ham UTC timestamp verince
        // Türkiye'de (UTC+3) grafik tam 3 saat geriyi gösteriyordu. Timestamp'i
        // yerel offset kadar kaydırarak kütüphanenin "UTC" render'ı yerel saati
        // göstermiş olur (kütüphanenin belgelenmiş yaklaşımı).
        time: Math.floor(
          (dateObj.getTime() - dateObj.getTimezoneOffset() * 60_000) / 1000
        ) as any,
        value: d.price,
      };
    }).sort((a, b) => a.time - b.time);

    // Remove duplicates by time if any exist
    const uniqueData = formattedData.filter(
      (value, index, self) => self.findIndex((t) => t.time === value.time) === index
    );

    // Determine colors based on overall return
    const isUp = uniqueData.length > 1 && uniqueData[uniqueData.length - 1].value >= uniqueData[0].value;
    const lineColor = isUp ? "#10b981" : "#ef4444";
    const topColor = isUp ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)";
    const bottomColor = isUp ? "rgba(16, 185, 129, 0.0)" : "rgba(239, 68, 68, 0.0)";

    // Clean up old chart
    if (chartRef.current) {
      chartRef.current.remove();
    }

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "rgba(55, 65, 81, 0.2)" },
        horzLines: { color: "rgba(55, 65, 81, 0.2)" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 320,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderVisible: false,
      },
      rightPriceScale: {
        borderVisible: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
      },
    });

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor: lineColor,
      topColor: topColor,
      bottomColor: bottomColor,
      lineWidth: 2,
      priceFormat: {
        type: "price",
        precision: 2,
        minMove: 0.01,
      },
    });

    areaSeries.setData(uniqueData);
    seriesRef.current = areaSeries;
    chartRef.current = chart;

    window.addEventListener("resize", handleResize);

    // Fit content
    chart.timeScale().fitContent();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [data, symbol]);

  return (
    <div className="w-full relative">
      <div className="absolute top-2 left-2 z-10 bg-gray-900/80 px-2.5 py-1 rounded text-xs text-gray-400 font-medium border border-gray-800">
        {symbol} / TRY (Canlı Grafiği)
      </div>
      <div ref={chartContainerRef} className="w-full h-[320px]" />
    </div>
  );
}
