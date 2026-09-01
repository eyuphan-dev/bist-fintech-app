"use client";

import React, { useEffect, useRef, useState } from "react";
import {
  createChart,
  ColorType,
  AreaSeries,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  LineStyle,
} from "lightweight-charts";
import { SlidersHorizontal, X, CandlestickChart, LineChart as LineChartIcon, Check } from "lucide-react";
import { marketColor, UP, DOWN } from "../../lib/marketColor";
import { API_BASE } from "../context/AuthContext";

interface ChartDataPoint {
  price: number;
  recorded_at: string;
  volume?: number | null;
  /** Yalnızca günlük (1H/1A/1Y/5Y) aralıklarda dolu gelir -- mum grafiği için gerekir. */
  open?: number | null;
  high?: number | null;
  low?: number | null;
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
  /** Seçili zaman aralığı kodu (1D/1W/1M/1Y/5Y) -- gösterge serisi bu aralık için çekilir. */
  range?: string;
}

interface Okuma {
  price: number;
  time: number;
  pct: number | null;
}

type OverlayKey = "sma20" | "sma50" | "sma200" | "ema20" | "bollinger";
type SubpaneKey = "hacim" | "rsi" | "macd" | "stochastic" | "adx" | "obv";

interface IndicatorSeriesData {
  available: boolean;
  dates: string[];
  sma20: (number | null)[];
  sma50: (number | null)[];
  sma200: (number | null)[];
  ema20: (number | null)[];
  bollinger_upper: (number | null)[];
  bollinger_mid: (number | null)[];
  bollinger_lower: (number | null)[];
  rsi14: (number | null)[];
  macd: (number | null)[];
  macd_signal: (number | null)[];
  macd_hist: (number | null)[];
  stochastic_k: (number | null)[];
  stochastic_d: (number | null)[];
  adx: (number | null)[];
  obv: (number | null)[];
}

const OVERLAY_TANIM: { key: OverlayKey; label: string; renk: string }[] = [
  { key: "sma20", label: "SMA 20", renk: "#F59E0B" },
  { key: "sma50", label: "SMA 50", renk: "#3B82F6" },
  { key: "sma200", label: "SMA 200", renk: "#A855F7" },
  { key: "ema20", label: "EMA 20", renk: "#EC4899" },
  { key: "bollinger", label: "Bollinger Bantları (20,2)", renk: "#8A99AD" },
];

const SUBPANE_TANIM: { key: SubpaneKey; label: string }[] = [
  { key: "hacim", label: "Hacim" },
  { key: "rsi", label: "RSI (14)" },
  { key: "macd", label: "MACD (12,26,9)" },
  { key: "stochastic", label: "Stochastic (14,3)" },
  { key: "adx", label: "ADX (14)" },
  { key: "obv", label: "OBV" },
];

// Mobilde ekranın altındaki paneller kalabalıklaşıp kullanılamaz hale
// gelmesin diye aynı anda en fazla bu kadar alt panel açılabilir. TradingView
// ve Midas'ın mobil uygulamaları da masaüstündeki gibi 4-5 paneli aynı anda
// açık tutmuyor.
const MAKS_ALT_PANEL = 2;
const TERCIH_ANAHTARI = "bist-grafik-gosterge-tercihi-v1";

interface Tercih {
  chartType: "alan" | "mum";
  overlays: OverlayKey[];
  subpanes: SubpaneKey[];
}

function loadTercih(): Tercih {
  if (typeof window === "undefined") return { chartType: "alan", overlays: [], subpanes: [] };
  try {
    const raw = window.localStorage.getItem(TERCIH_ANAHTARI);
    if (!raw) return { chartType: "alan", overlays: [], subpanes: [] };
    const parsed = JSON.parse(raw);
    return {
      chartType: parsed.chartType === "mum" ? "mum" : "alan",
      overlays: Array.isArray(parsed.overlays) ? parsed.overlays : [],
      subpanes: Array.isArray(parsed.subpanes) ? parsed.subpanes.slice(0, MAKS_ALT_PANEL) : [],
    };
  } catch {
    return { chartType: "alan", overlays: [], subpanes: [] };
  }
}

function saveTercih(v: Tercih) {
  try {
    window.localStorage.setItem(TERCIH_ANAHTARI, JSON.stringify(v));
  } catch {
    // localStorage kapalı/dolu olabilir -- tercih o oturumda hafızada kalır, kritik değil.
  }
}

/**
 * ISO tarih/zaman damgasını lightweight-charts'ın zaman eksenine çevirir.
 *
 * Kütüphane zaman etiketlerini HER ZAMAN UTC olarak render eder ve saat
 * dilimi ayarı yoktur. Ham UTC timestamp verince Türkiye'de (UTC+3) grafik
 * 3 saat geriyi gösteriyordu. Timestamp'i yerel offset kadar kaydırarak
 * kütüphanenin "UTC" render'ı yerel saati göstermiş olur (belgelenmiş
 * yaklaşım). Fiyat serisi VE gösterge serisi aynı fonksiyonu kullanmalı,
 * aksi halde ikisi grafikte aynı gün üzerine denk gelmez.
 */
function toChartTime(iso: string): number {
  const d = new Date(iso);
  return Math.floor((d.getTime() - d.getTimezoneOffset() * 60_000) / 1000);
}

/**
 * Hisse fiyat grafiği + isteğe bağlı gösterge katmanları (TradingView/Midas
 * tarzı "gösterge ekle").
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
  range = "1Y",
}: TradingViewChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const [okuma, setOkuma] = useState<Okuma | null>(null);
  const [sonOkuma, setSonOkuma] = useState<Okuma | null>(null);

  const [tercih, setTercih] = useState<Tercih>(loadTercih);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [indicatorData, setIndicatorData] = useState<IndicatorSeriesData | null>(null);

  // Gün içi (1D) aralıkta yüksek/düşük/açılış yok -- göstergelerin çoğu
  // (Bollinger, Stochastic, ADX) tanımı gereği bunlara ihtiyaç duyar.
  const gostergeDesteklenir = !intraday;
  const gostergeSecili = tercih.overlays.length > 0 || tercih.subpanes.length > 0;

  useEffect(() => {
    saveTercih(tercih);
  }, [tercih]);

  useEffect(() => {
    // Sembol/aralık değişir değişmez ÖNCEKİ verisi hemen temizlenir. Aksi
    // halde yeni istek tamamlanana kadar (yavaş ağda gözle görülür bir süre)
    // eski hissenin SMA/RSI serisi yeni hissenin fiyat grafiğinin üstüne
    // yanlışlıkla çizilmiş olurdu -- iki farklı sembol aynı overlay'i paylaşır.
    setIndicatorData(null);
    if (!gostergeDesteklenir || !gostergeSecili) return;

    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/indicator-series?range=${range}`);
        if (!res.ok) return;
        const json = await res.json();
        if (!cancelled) setIndicatorData(json.available ? json : null);
      } catch {
        if (!cancelled) setIndicatorData(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [symbol, range, gostergeDesteklenir, gostergeSecili]);

  const toggleOverlay = (key: OverlayKey) => {
    setTercih((t) => ({
      ...t,
      overlays: t.overlays.includes(key) ? t.overlays.filter((k) => k !== key) : [...t.overlays, key],
    }));
  };

  const toggleSubpane = (key: SubpaneKey) => {
    setTercih((t) => {
      if (t.subpanes.includes(key)) return { ...t, subpanes: t.subpanes.filter((k) => k !== key) };
      if (t.subpanes.length >= MAKS_ALT_PANEL) return t;
      return { ...t, subpanes: [...t.subpanes, key] };
    });
  };

  useEffect(() => {
    if (!chartContainerRef.current || data.length === 0) return;

    const formattedData = data
      .map((d) => ({
        time: toChartTime(d.recorded_at) as any,
        value: d.price,
        open: d.open ?? d.price,
        high: d.high ?? d.price,
        low: d.low ?? d.price,
        close: d.price,
        volume: d.volume ?? 0,
      }))
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
    const lineColor = isUp ? UP : DOWN;
    const topColor = isUp ? "rgba(16, 185, 129, 0.3)" : "rgba(244, 63, 94, 0.3)";
    const bottomColor = isUp ? "rgba(16, 185, 129, 0.0)" : "rgba(244, 63, 94, 0.0)";

    if (chartRef.current) {
      chartRef.current.remove();
    }

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    // Mum grafiği yalnızca OHLC dolu geldiğinde (1D dışındaki aralıklar) seçilebilir.
    const canCandlestick = gostergeDesteklenir && data.every((d) => d.open != null && d.high != null && d.low != null);
    const gosterimTuru = canCandlestick ? tercih.chartType : "alan";

    const ANA_YUKSEKLIK = 320;
    const ALT_YUKSEKLIK = 110;
    const toplamYukseklik = ANA_YUKSEKLIK + tercih.subpanes.length * ALT_YUKSEKLIK;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
        panes: { enableResize: false, separatorColor: "#242B35", separatorHoverColor: "#242B35" },
      },
      grid: {
        vertLines: { color: "rgba(55, 65, 81, 0.2)" },
        horzLines: { color: "rgba(55, 65, 81, 0.2)" },
      },
      width: chartContainerRef.current.clientWidth,
      height: toplamYukseklik,
      timeScale: { timeVisible: true, secondsVisible: false, borderVisible: false },
      // Üst boşluk büyütüldü: Bollinger üst bandı fiyat serisinin en yüksek
      // noktasının BELİRGİN ÜSTÜNE çıkabiliyor. Bu boşluk olmadan seri
      // panelin en tepesine kadar dayanıyor ve sol üstteki sabit fiyat/yüzde
      // şeridiyle eksen etiketleri ("260.00" gibi) üst üste biniyordu.
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.14, bottom: 0.05 } },
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

    // --- Ana seri (fiyat) ---
    let mainSeries: any;
    if (gosterimTuru === "mum") {
      mainSeries = chart.addSeries(CandlestickSeries, {
        upColor: UP,
        downColor: DOWN,
        borderVisible: false,
        wickUpColor: UP,
        wickDownColor: DOWN,
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      mainSeries.setData(
        uniqueData.map((d) => ({ time: d.time, open: d.open, high: d.high, low: d.low, close: d.close }))
      );
    } else {
      mainSeries = chart.addSeries(AreaSeries, {
        lineColor,
        topColor,
        bottomColor,
        lineWidth: 2,
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      mainSeries.setData(uniqueData.map((d) => ({ time: d.time, value: d.value })));
    }

    // Referans çizgisi: yüzdenin neye göre okunduğu görünür olmalı, yoksa
    // "%+2,4" sayısı havada kalır.
    mainSeries.createPriceLine({
      price: ref,
      color: "rgba(138, 153, 173, 0.45)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      axisLabelVisible: false,
      title: "",
    });

    // --- Ana panelin üstüne bindirilen göstergeler (SMA/EMA/Bollinger) ---
    if (indicatorData && gostergeDesteklenir) {
      const idxTime = indicatorData.dates.map((d) => toChartTime(d));
      const buildLineData = (values: (number | null)[]) =>
        idxTime
          .map((t, i) => ({ time: t as any, value: values[i] }))
          .filter((p): p is { time: any; value: number } => p.value !== null && p.value !== undefined);

      const overlayCizgi = (key: OverlayKey, values: (number | null)[], renk: string) => {
        if (!tercih.overlays.includes(key)) return;
        const s = chart.addSeries(LineSeries, { color: renk, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        s.setData(buildLineData(values));
      };

      overlayCizgi("sma20", indicatorData.sma20, "#F59E0B");
      overlayCizgi("sma50", indicatorData.sma50, "#3B82F6");
      overlayCizgi("sma200", indicatorData.sma200, "#A855F7");
      overlayCizgi("ema20", indicatorData.ema20, "#EC4899");

      if (tercih.overlays.includes("bollinger")) {
        [indicatorData.bollinger_upper, indicatorData.bollinger_lower].forEach((seri) => {
          const s = chart.addSeries(LineSeries, {
            color: "rgba(138,153,173,0.55)",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: false,
          });
          s.setData(buildLineData(seri));
        });
        const orta = chart.addSeries(LineSeries, {
          color: "rgba(138,153,173,0.35)",
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        });
        orta.setData(buildLineData(indicatorData.bollinger_mid));
      }
    }

    // --- Alt paneller (RSI/MACD/Stochastic/ADX/OBV/Hacim) ---
    // Alt paneller SEÇİM SIRASINA göre değil, SUBPANE_TANIM'daki sabit sıraya
    // göre çizilir -- aksi halde "önce RSI sonra Hacim" seçen kullanıcı ile
    // "önce Hacim sonra RSI" seçen kullanıcı aynı iki göstergede farklı bir
    // panel düzeni görürdü, bu da tutarsız ve şaşırtıcı olurdu.
    const siraliSubpaneler = SUBPANE_TANIM.map((t) => t.key).filter((key) => tercih.subpanes.includes(key));
    siraliSubpaneler.forEach((key) => {
      const pane = chart.addPane();
      pane.setHeight(ALT_YUKSEKLIK);
      const paneIndex = pane.paneIndex();

      if (key === "hacim") {
        const hs = chart.addSeries(
          HistogramSeries,
          { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false },
          paneIndex
        );
        hs.setData(
          uniqueData.map((d, i) => ({
            time: d.time,
            value: d.volume,
            color: i === 0 || d.close >= uniqueData[i - 1].close ? "rgba(16,185,129,0.55)" : "rgba(244,63,94,0.55)",
          }))
        );
        return;
      }

      if (!indicatorData) return;
      const idxTime = indicatorData.dates.map((d) => toChartTime(d));
      const buildLineData = (values: (number | null)[]) =>
        idxTime
          .map((t, i) => ({ time: t as any, value: values[i] }))
          .filter((p): p is { time: any; value: number } => p.value !== null && p.value !== undefined);

      if (key === "rsi") {
        const s = chart.addSeries(LineSeries, { color: "#22D3EE", lineWidth: 2, priceLineVisible: false }, paneIndex);
        s.setData(buildLineData(indicatorData.rsi14));
        [30, 70].forEach((seviye) =>
          s.createPriceLine({
            price: seviye,
            color: "rgba(138,153,173,0.4)",
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: "",
          })
        );
      } else if (key === "macd") {
        const histData = indicatorData.macd_hist
          .map((v, i) => ({ time: idxTime[i] as any, value: v, orijinal: v }))
          .filter((p) => p.orijinal !== null && p.orijinal !== undefined)
          .map((p) => ({ time: p.time, value: p.value as number, color: (p.value as number) >= 0 ? "rgba(16,185,129,0.6)" : "rgba(244,63,94,0.6)" }));
        const hist = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, paneIndex);
        hist.setData(histData);
        const macdLine = chart.addSeries(
          LineSeries,
          { color: "#3B82F6", lineWidth: 2, priceLineVisible: false, lastValueVisible: false },
          paneIndex
        );
        macdLine.setData(buildLineData(indicatorData.macd));
        const sinyalLine = chart.addSeries(
          LineSeries,
          { color: "#F59E0B", lineWidth: 2, priceLineVisible: false, lastValueVisible: false },
          paneIndex
        );
        sinyalLine.setData(buildLineData(indicatorData.macd_signal));
      } else if (key === "stochastic") {
        const kLine = chart.addSeries(LineSeries, { color: "#22D3EE", lineWidth: 2, priceLineVisible: false }, paneIndex);
        kLine.setData(buildLineData(indicatorData.stochastic_k));
        const dLine = chart.addSeries(
          LineSeries,
          { color: "#F59E0B", lineWidth: 2, priceLineVisible: false, lastValueVisible: false },
          paneIndex
        );
        dLine.setData(buildLineData(indicatorData.stochastic_d));
      } else if (key === "adx") {
        const s = chart.addSeries(LineSeries, { color: "#EAB308", lineWidth: 2, priceLineVisible: false }, paneIndex);
        s.setData(buildLineData(indicatorData.adx));
      } else if (key === "obv") {
        const s = chart.addSeries(LineSeries, { color: "#8A99AD", lineWidth: 2, priceLineVisible: false }, paneIndex);
        s.setData(buildLineData(indicatorData.obv));
      }
    });

    chart.subscribeCrosshairMove((param: any) => {
      if (!param.time || !param.point) {
        setOkuma(null);
        return;
      }
      const nokta = param.seriesData.get(mainSeries) as { value?: number; close?: number } | undefined;
      const deger = nokta?.value ?? nokta?.close;
      if (deger === undefined) {
        setOkuma(null);
        return;
      }
      setOkuma({ price: deger, time: param.time as number, pct: yuzde(deger) });
    });

    chartRef.current = chart;
    window.addEventListener("resize", handleResize);
    chart.timeScale().fitContent();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [data, symbol, baseline, tercih, indicatorData, gostergeDesteklenir]);

  const gosterilen = okuma ?? sonOkuma;
  const pct = gosterilen?.pct ?? null;
  const pctRenk = marketColor(pct);

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

  const canCandlestickToggle = gostergeDesteklenir && data.every((d) => d.open != null && d.high != null && d.low != null);
  const secimSayisi = tercih.overlays.length + tercih.subpanes.length;

  return (
    <div className="w-full relative">
      {/* Grafik türü + gösterge seçim araç çubuğu -- fiyat okuma şeridiyle
          çakışmaması için ayrı bir satırda, chart container'ın DIŞINDA. */}
      {gostergeDesteklenir && (
        <div className="flex items-center justify-end gap-1.5 mb-1.5">
          {canCandlestickToggle && (
            <div className="flex items-center bg-[#0B0E14] border border-[#242B35] rounded-lg overflow-hidden">
              <button
                onClick={() => setTercih((t) => ({ ...t, chartType: "alan" }))}
                title="Alan grafiği"
                className={`p-1.5 transition ${tercih.chartType === "alan" ? "bg-[#10B981] text-[#0B0E14]" : "text-gray-500 hover:text-white"}`}
              >
                <LineChartIcon className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setTercih((t) => ({ ...t, chartType: "mum" }))}
                title="Mum grafiği"
                className={`p-1.5 transition ${tercih.chartType === "mum" ? "bg-[#10B981] text-[#0B0E14]" : "text-gray-500 hover:text-white"}`}
              >
                <CandlestickChart className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
          <button
            onClick={() => setPickerOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-[#0B0E14] border border-[#242B35] text-gray-400 hover:text-white transition"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            Göstergeler
            {secimSayisi > 0 && (
              <span className="bg-[#10B981] text-[#0B0E14] rounded-full w-4 h-4 flex items-center justify-center text-[9px] font-bold">
                {secimSayisi}
              </span>
            )}
          </button>
        </div>
      )}

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
        <div ref={chartContainerRef} className="w-full" style={{ height: 320 + tercih.subpanes.length * 110 }} />
      </div>

      {pickerOpen && gostergeDesteklenir && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setPickerOpen(false)}
        >
          <div
            className="relative w-full sm:max-w-md bg-[#151921] border border-[#242B35] rounded-t-2xl sm:rounded-2xl max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-[#151921] border-b border-[#242B35] px-4 py-3 flex items-center justify-between">
              <h3 className="text-sm font-bold text-white">Grafik Göstergeleri</h3>
              <button onClick={() => setPickerOpen(false)} className="text-gray-500 hover:text-white transition" title="Kapat">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 space-y-5">
              <div>
                <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Fiyat üzerine bindirilir
                </p>
                <div className="space-y-1">
                  {OVERLAY_TANIM.map((o) => {
                    const secili = tercih.overlays.includes(o.key);
                    return (
                      <button
                        key={o.key}
                        onClick={() => toggleOverlay(o.key)}
                        className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-xs font-medium transition ${
                          secili ? "bg-[#10B981]/10 text-white" : "text-gray-400 hover:bg-[#0B0E14]"
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: o.renk }} />
                          {o.label}
                        </span>
                        {secili && <Check className="w-3.5 h-3.5 text-[#10B981]" />}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">Alt panel</p>
                  <p className="text-[10px] text-gray-600">{tercih.subpanes.length}/{MAKS_ALT_PANEL} seçili</p>
                </div>
                <div className="space-y-1">
                  {SUBPANE_TANIM.map((s) => {
                    const secili = tercih.subpanes.includes(s.key);
                    const devreDisi = !secili && tercih.subpanes.length >= MAKS_ALT_PANEL;
                    return (
                      <button
                        key={s.key}
                        onClick={() => toggleSubpane(s.key)}
                        disabled={devreDisi}
                        className={`w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg text-xs font-medium transition ${
                          secili
                            ? "bg-[#10B981]/10 text-white"
                            : devreDisi
                            ? "text-gray-700 cursor-not-allowed"
                            : "text-gray-400 hover:bg-[#0B0E14]"
                        }`}
                      >
                        {s.label}
                        {secili && <Check className="w-3.5 h-3.5 text-[#10B981]" />}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[10px] text-gray-600 mt-2">
                  Küçük ekranda okunabilirlik için aynı anda en fazla {MAKS_ALT_PANEL} alt panel açılabilir.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
