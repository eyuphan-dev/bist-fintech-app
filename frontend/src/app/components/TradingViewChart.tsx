"use client";

import React, { useEffect, useRef, useState } from "react";
import { createChart, ColorType, ISeriesApi, AreaSeries, LineStyle } from "lightweight-charts";

interface ChartDataPoint {
  price: number;
  recorded_at: string;
}

interface TradingViewChartProps {
  data: ChartDataPoint[];
  symbol: string;
  /**
   * Yüzde değişimin ölçüleceği referans. Gün içi grafikte önceki kapanış
   * verilir; verilmezse aralığın ilk noktası kullanılır (ör. 1 yıllık
   * grafikte "yıl başından bu yana" anlamına gelir).
   */
  baseline?: number | null;
  /** Gün içi aralıkta saat de gösterilir; uzun aralıklarda yalnızca tarih. */
  intraday?: boolean;
}

interface Okuma {
  price: number;
  time: number;
  pct: number | null;
}

/**
 * Hisse fiyat grafiği.
 *
 * İMLEÇ OKUMASI: Grafiğin üstündeki şerit, imlecin/parmağın bulunduğu andaki
 * fiyatı VE referansa göre yüzde değişimi gösterir. Bu, Midas gibi
 * uygulamalarda olup bizde eksik olan parçaydı: kullanıcı grafikte bir noktaya
 * bakıp "burada ne kadardı" sorusunu ancak sayıyı görüyorsa cevaplayabiliyor,
 * yüzdeyi kafadan hesaplaması gerekiyordu.
 *
 * Neden yüzen (floating) balon değil de sabit şerit: dokunmatik ekranda parmak
 * balonun üstünü kapatıyor ve balon ekranın kenarına taşıyor. Sabit şerit her
 * cihazda aynı yerde durur, parmak altında kalmaz.
 */
export default function TradingViewChart({
  data,
  symbol,
  baseline = null,
  intraday = false,
}: TradingViewChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const [okuma, setOkuma] = useState<Okuma | null>(null);
  const [sonOkuma, setSonOkuma] = useState<Okuma | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    const formattedData = data
      .map((d) => {
        const dateObj = new Date(d.recorded_at);
        // lightweight-charts zaman etiketlerini HER ZAMAN UTC olarak render eder
        // ve kütüphanenin saat dilimi ayarı yoktur. Ham UTC timestamp verince
        // Türkiye'de (UTC+3) grafik tam 3 saat geriyi gösteriyordu. Timestamp'i
        // yerel offset kadar kaydırarak kütüphanenin "UTC" render'ı yerel saati
        // göstermiş olur (kütüphanenin belgelenmiş yaklaşımı).
        return {
          time: Math.floor(
            (dateObj.getTime() - dateObj.getTimezoneOffset() * 60_000) / 1000
          ) as any,
          value: d.price,
        };
      })
      .sort((a, b) => a.time - b.time);

    const uniqueData = formattedData.filter(
      (value, index, self) => self.findIndex((t) => t.time === value.time) === index
    );
    if (uniqueData.length === 0) return;

    // Referans: verilmişse önceki kapanış, yoksa aralığın ilk noktası.
    const ref = baseline && baseline > 0 ? baseline : uniqueData[0].value;
    const yuzde = (v: number) => (ref > 0 ? ((v - ref) / ref) * 100 : null);

    const son = uniqueData[uniqueData.length - 1];
    setSonOkuma({ price: son.value, time: son.time, pct: yuzde(son.value) });
    setOkuma(null);

    const isUp = son.value >= ref;
    const lineColor = isUp ? "#10b981" : "#ef4444";
    const topColor = isUp ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)";
    const bottomColor = isUp ? "rgba(16, 185, 129, 0.0)" : "rgba(239, 68, 68, 0.0)";

    if (chartRef.current) {
      chartRef.current.remove();
    }

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
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
      timeScale: { timeVisible: true, secondsVisible: false, borderVisible: false },
      rightPriceScale: { borderVisible: false },
      handleScale: { axisPressedMouseMove: true },
      crosshair: {
        // Dikey çizgi serbest hareket etsin, yatay çizgi veri noktasına
        // kilitlensin: kullanıcı okuduğu fiyatın gerçek bir veri noktası
        // olduğundan emin olmalı.
        mode: 1,
        vertLine: { color: "#4B5563", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#242B35" },
        horzLine: { color: "#4B5563", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#242B35" },
      },
    });

    const areaSeries = chart.addSeries(AreaSeries, {
      lineColor,
      topColor,
      bottomColor,
      lineWidth: 2,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });

    areaSeries.setData(uniqueData);

    // Referans çizgisi: yüzdenin neye göre okunduğu görünür olmalı, yoksa
    // "%+2,4" sayısı havada kalır.
    areaSeries.createPriceLine({
      price: ref,
      color: "rgba(138, 153, 173, 0.45)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: false,
      title: "",
    });

    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point) {
        setOkuma(null);
        return;
      }
      const nokta = param.seriesData.get(areaSeries) as { value?: number } | undefined;
      if (!nokta || nokta.value === undefined) {
        setOkuma(null);
        return;
      }
      setOkuma({ price: nokta.value, time: param.time as number, pct: yuzde(nokta.value) });
    });

    seriesRef.current = areaSeries;
    chartRef.current = chart;
    window.addEventListener("resize", handleResize);
    chart.timeScale().fitContent();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [data, symbol, baseline]);

  const gosterilen = okuma ?? sonOkuma;
  const pct = gosterilen?.pct ?? null;
  const pctRenk = pct === null ? "#8A99AD" : pct >= 0 ? "#10B981" : "#F43F5E";

  const zamanMetni = (() => {
    if (!gosterilen) return "";
    // Zaman damgası çizim için yerel offset kadar kaydırılmıştı; okunurken
    // aynı kaydırma geri alınmadan UTC olarak biçimlendirilir, böylece
    // grafikteki eksen etiketiyle birebir aynı saati gösterir.
    const d = new Date(gosterilen.time * 1000);
    const tarih = `${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}.${d.getUTCFullYear()}`;
    if (!intraday) return tarih;
    return `${tarih} ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  })();

  return (
    <div className="w-full relative">
      {/* İmleç okuma şeridi — imleç yokken son değeri gösterir, yani hiçbir
          zaman boş kalmaz. */}
      <div className="absolute top-2 left-2 right-2 z-10 flex items-center justify-between gap-2 pointer-events-none">
        <div className="bg-[#0B0E14]/85 backdrop-blur px-2.5 py-1.5 rounded-lg border border-[#242B35] flex items-baseline gap-2 min-w-0">
          <span className="text-[10px] text-gray-500 font-semibold shrink-0">{symbol}</span>
          {gosterilen && (
            <>
              <span className="text-xs font-bold text-white tabular-nums">
                {gosterilen.price.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className="text-xs font-bold tabular-nums" style={{ color: pctRenk }}>
                {pct === null
                  ? "—"
                  : `${pct >= 0 ? "+" : "−"}%${Math.abs(pct).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              </span>
            </>
          )}
        </div>
        {gosterilen && (
          <span className="text-[10px] text-gray-500 tabular-nums bg-[#0B0E14]/85 backdrop-blur px-2 py-1 rounded-lg border border-[#242B35] shrink-0">
            {zamanMetni}
          </span>
        )}
      </div>
      <div ref={chartContainerRef} className="w-full h-[320px]" />
    </div>
  );
}
