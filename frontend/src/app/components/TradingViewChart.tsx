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
import {
  SlidersHorizontal,
  X,
  CandlestickChart,
  LineChart as LineChartIcon,
  Check,
  TrendingUp,
  Zap,
  Layers,
  BarChart3,
  Activity,
  Waves,
  ArrowUpDown,
  Gauge,
  RotateCcw,
  PanelBottom,
  Anchor,
  Flame,
  Percent,
  Radar,
  Droplets,
  FunctionSquare,
} from "lucide-react";
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

type OverlayKey = "sma20" | "sma50" | "sma200" | "ema20" | "bollinger" | "vwap" | "supertrend";
type SubpaneKey = "hacim" | "rsi" | "macd" | "stochastic" | "adx" | "obv" | "williams_r" | "cci" | "mfi";

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
  supertrend_up: (number | null)[];
  supertrend_down: (number | null)[];
  williams_r: (number | null)[];
  cci: (number | null)[];
  mfi: (number | null)[];
  vwap: (number | null)[];
}

const OVERLAY_TANIM: { key: OverlayKey; label: string; renk: string; aciklama: string; icon: any }[] = [
  { key: "sma20", label: "SMA 20", renk: "#F59E0B", aciklama: "Kısa vadeli trend ortalaması", icon: TrendingUp },
  { key: "sma50", label: "SMA 50", renk: "#3B82F6", aciklama: "Orta vadeli trend ortalaması", icon: TrendingUp },
  { key: "sma200", label: "SMA 200", renk: "#A855F7", aciklama: "Uzun vadeli trend ortalaması", icon: TrendingUp },
  { key: "ema20", label: "EMA 20", renk: "#EC4899", aciklama: "Son fiyatlara daha duyarlı ortalama", icon: Zap },
  { key: "bollinger", label: "Bollinger Bantları", renk: "#8A99AD", aciklama: "Volatilite bandı — dar/geniş açılım", icon: Layers },
  { key: "vwap", label: "VWAP (Haftalık)", renk: "#22D3EE", aciklama: "Hacim ağırlıklı ortalama fiyat, adil değer referansı", icon: Anchor },
  { key: "supertrend", label: "SuperTrend", renk: "#F97316", aciklama: "Tek çizgiyle trend yönü — altında al, üstünde sat", icon: Flame },
];

const SUBPANE_TANIM: { key: SubpaneKey; label: string; aciklama: string; icon: any }[] = [
  { key: "hacim", label: "Hacim", aciklama: "İşlem hacmi, her hareketin arkasındaki güç", icon: BarChart3 },
  { key: "rsi", label: "RSI (14)", aciklama: "Aşırı alım/satım ölçer (0-100)", icon: Activity },
  { key: "macd", label: "MACD (12,26,9)", aciklama: "İki ortalama arasındaki fark, trend dönüşü", icon: Waves },
  { key: "stochastic", label: "Stochastic (14,3)", aciklama: "Kapanışın son bandın neresinde olduğu", icon: ArrowUpDown },
  { key: "adx", label: "ADX (14)", aciklama: "Trendin GÜCÜNÜ ölçer, yönünü değil", icon: Gauge },
  { key: "obv", label: "OBV", aciklama: "Hacmin yönlü birikimi", icon: LineChartIcon },
  { key: "williams_r", label: "Williams %R (14)", aciklama: "Stochastic'in ters ölçekli hali (-100..0)", icon: Percent },
  { key: "cci", label: "CCI (20)", aciklama: "Fiyatın ortalamadan sapması, dönüş sinyali", icon: Radar },
  { key: "mfi", label: "MFI (14)", aciklama: "Hacimli RSI — fiyat + hacmi birlikte ölçer", icon: Droplets },
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

// --- Kendi formülünü kurma (TradingView Pine Script'in çok basitleştirilmiş,
// güvenli hali -- bkz. backend/custom_indicator.py: formül asla eval/exec ile
// çalıştırılmaz, whitelist'li bir AST yorumlayıcısından geçer). ---
interface OzelFormul {
  id: string;
  formula: string;
  hedef: "overlay" | "subpane";
  renk: string;
  aktif: boolean;
}

const OZEL_FORMUL_ANAHTARI = "bist-ozel-formuller-v1";
const MAKS_OZEL_FORMUL = 5;
const OZEL_FORMUL_RENK_PALETI = ["#E879F9", "#FB923C", "#4ADE80", "#60A5FA", "#FCD34D"];

function loadOzelFormuller(): OzelFormul[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(OZEL_FORMUL_ANAHTARI);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, MAKS_OZEL_FORMUL) : [];
  } catch {
    return [];
  }
}

function saveOzelFormuller(v: OzelFormul[]) {
  try {
    window.localStorage.setItem(OZEL_FORMUL_ANAHTARI, JSON.stringify(v));
  } catch {
    // kritik değil, oturum içinde hafızada kalır.
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

  const [ozelFormuller, setOzelFormuller] = useState<OzelFormul[]>(loadOzelFormuller);
  const [ozelFormulVeri, setOzelFormulVeri] = useState<Record<string, { available: boolean; dates: string[]; values: (number | null)[] }>>({});
  const [formulMetni, setFormulMetni] = useState("");
  const [formulHedef, setFormulHedef] = useState<"overlay" | "subpane">("subpane");
  const [formulHata, setFormulHata] = useState<string | null>(null);
  const [formulYukleniyor, setFormulYukleniyor] = useState(false);

  // Gün içi (1D) aralıkta yüksek/düşük/açılış yok -- göstergelerin çoğu
  // (Bollinger, Stochastic, ADX) tanımı gereği bunlara ihtiyaç duyar.
  const gostergeDesteklenir = !intraday;
  const aktifOzelAltPaneller = ozelFormuller.filter((f) => f.aktif && f.hedef === "subpane");
  const aktifOzelOverlaylar = ozelFormuller.filter((f) => f.aktif && f.hedef === "overlay");
  // Mobilde ekran kalabalıklaşmasın diye özel formüller de aynı alt panel
  // sınırını (MAKS_ALT_PANEL) hazır göstergelerle PAYLAŞIR -- ayrı bir sınır
  // olsaydı kullanıcı 2 hazır + 2 özel = 4 panel açıp mobilde aynı soruna
  // geri dönerdi.
  const toplamAltPanelSayisi = tercih.subpanes.length + aktifOzelAltPaneller.length;
  const gostergeSecili = tercih.overlays.length > 0 || tercih.subpanes.length > 0 || ozelFormuller.some((f) => f.aktif);

  useEffect(() => {
    saveTercih(tercih);
  }, [tercih]);

  useEffect(() => {
    saveOzelFormuller(ozelFormuller);
  }, [ozelFormuller]);

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

  // Aktif özel formüllerin serisini çeker. Her formül ayrı bir kullanıcı
  // ifadesi olduğu için tek bir toplu uçtan (indicator-series gibi) gelemez
  // -- her biri kendi POST isteğiyle hesaplanır.
  useEffect(() => {
    const aktifler = ozelFormuller.filter((f) => f.aktif);
    if (!gostergeDesteklenir || aktifler.length === 0) {
      setOzelFormulVeri({});
      return;
    }
    let cancelled = false;
    (async () => {
      const sonuclar: Record<string, { available: boolean; dates: string[]; values: (number | null)[] }> = {};
      await Promise.all(
        aktifler.map(async (f) => {
          try {
            const res = await fetch(`${API_BASE}/stocks/${symbol}/custom-indicator?range=${range}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ formula: f.formula }),
            });
            const json = await res.json();
            sonuclar[f.id] = json;
          } catch {
            sonuclar[f.id] = { available: false, dates: [], values: [] };
          }
        })
      );
      if (!cancelled) setOzelFormulVeri(sonuclar);
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, range, gostergeDesteklenir, JSON.stringify(ozelFormuller.filter((f) => f.aktif).map((f) => [f.id, f.formula]))]);

  const toggleOverlay = (key: OverlayKey) => {
    setTercih((t) => ({
      ...t,
      overlays: t.overlays.includes(key) ? t.overlays.filter((k) => k !== key) : [...t.overlays, key],
    }));
  };

  const toggleSubpane = (key: SubpaneKey) => {
    setTercih((t) => {
      if (t.subpanes.includes(key)) return { ...t, subpanes: t.subpanes.filter((k) => k !== key) };
      if (toplamAltPanelSayisi >= MAKS_ALT_PANEL) return t;
      return { ...t, subpanes: [...t.subpanes, key] };
    });
  };

  const sifirlaGostergeler = () => {
    setTercih((t) => ({ ...t, overlays: [], subpanes: [] }));
    setOzelFormuller((fs) => fs.map((f) => ({ ...f, aktif: false })));
  };

  const formulEkle = async () => {
    const formula = formulMetni.trim();
    if (!formula) return;
    if (ozelFormuller.length >= MAKS_OZEL_FORMUL) {
      setFormulHata(`En fazla ${MAKS_OZEL_FORMUL} özel formül kaydedebilirsiniz.`);
      return;
    }
    if (formulHedef === "subpane" && toplamAltPanelSayisi >= MAKS_ALT_PANEL) {
      setFormulHata(`Alt panel dolu (en fazla ${MAKS_ALT_PANEL}). "Fiyat üzerine" seçip ekleyebilir ya da bir paneli kapatabilirsiniz.`);
      return;
    }
    setFormulHata(null);
    setFormulYukleniyor(true);
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/custom-indicator?range=${range}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ formula }),
      });
      const json = await res.json();
      if (!json.available) {
        setFormulHata(json.reason || "Formül hesaplanamadı.");
        return;
      }
      const renk = OZEL_FORMUL_RENK_PALETI[ozelFormuller.length % OZEL_FORMUL_RENK_PALETI.length];
      const yeni: OzelFormul = { id: `${Date.now()}`, formula, hedef: formulHedef, renk, aktif: true };
      setOzelFormuller((fs) => [...fs, yeni]);
      setFormulMetni("");
    } catch {
      setFormulHata("Sunucuya ulaşılamadı, tekrar deneyin.");
    } finally {
      setFormulYukleniyor(false);
    }
  };

  const formulSil = (id: string) => setOzelFormuller((fs) => fs.filter((f) => f.id !== id));

  const formulAcKapat = (id: string) => {
    setOzelFormuller((fs) => {
      const hedefFormul = fs.find((f) => f.id === id);
      if (hedefFormul && !hedefFormul.aktif && hedefFormul.hedef === "subpane" && toplamAltPanelSayisi >= MAKS_ALT_PANEL) {
        return fs; // alt panel dolu -- açılamaz
      }
      return fs.map((f) => (f.id === id ? { ...f, aktif: !f.aktif } : f));
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
    const toplamYukseklik = ANA_YUKSEKLIK + toplamAltPanelSayisi * ALT_YUKSEKLIK;

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

      // NEDEN AÇIK CAM GÖBEĞİ: koyu teal (#14B8A6 gibi) alan grafiğinin
      // kendi yeşil dolgusuna görsel olarak çok yakın kalıyor ve ince
      // çizgi neredeyse kayboluyordu (ölçüldü). Yüksek parlaklıktaki
      // #22D3EE her zeminde net ayırt ediliyor.
      overlayCizgi("vwap", indicatorData.vwap, "#22D3EE");

      if (tercih.overlays.includes("supertrend")) {
        // İki ayrı seri: yükseliş/düşüş bölümleri farklı renklerde --
        // lightweight-charts'ta tek seri nokta başına renk değiştiremiyor.
        // NEDEN UP/DOWN (yeşil/kırmızı) DEĞİL: "Alan" grafik türünde fiyat
        // serisinin dolgusu zaten yeşil -- SuperTrend'i de yeşil çizince
        // aynı renk üst üste binip görünmez oluyordu (ölçüldü, ekran
        // görüntüsünde SuperTrend'in yükseliş bölümü fark edilmiyordu).
        // Amber/mor ikilisi hem alan hem mum modunda her zaman ayırt edilir.
        const yukselis = chart.addSeries(LineSeries, { color: "#FBBF24", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        yukselis.setData(buildLineData(indicatorData.supertrend_up));
        const dusus = chart.addSeries(LineSeries, { color: "#8B5CF6", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        dusus.setData(buildLineData(indicatorData.supertrend_down));
      }
    }

    // --- Kullanıcının kendi formülleri (fiyat üzerine) ---
    if (gostergeDesteklenir) {
      aktifOzelOverlaylar.forEach((f) => {
        const veri = ozelFormulVeri[f.id];
        if (!veri || !veri.available) return;
        const zamanlar = veri.dates.map((d) => toChartTime(d));
        const noktalar = zamanlar
          .map((t, i) => ({ time: t as any, value: veri.values[i] }))
          .filter((p): p is { time: any; value: number } => p.value !== null && p.value !== undefined);
        const s = chart.addSeries(LineSeries, { color: f.renk, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
        s.setData(noktalar);
      });
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
      } else if (key === "williams_r") {
        const s = chart.addSeries(LineSeries, { color: "#0EA5E9", lineWidth: 2, priceLineVisible: false }, paneIndex);
        s.setData(buildLineData(indicatorData.williams_r));
        [-20, -80].forEach((seviye) =>
          s.createPriceLine({
            price: seviye,
            color: "rgba(138,153,173,0.4)",
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: "",
          })
        );
      } else if (key === "cci") {
        const s = chart.addSeries(LineSeries, { color: "#F472B6", lineWidth: 2, priceLineVisible: false }, paneIndex);
        s.setData(buildLineData(indicatorData.cci));
      } else if (key === "mfi") {
        const s = chart.addSeries(LineSeries, { color: "#84CC16", lineWidth: 2, priceLineVisible: false }, paneIndex);
        s.setData(buildLineData(indicatorData.mfi));
        [20, 80].forEach((seviye) =>
          s.createPriceLine({
            price: seviye,
            color: "rgba(138,153,173,0.4)",
            lineWidth: 1,
            lineStyle: LineStyle.Dotted,
            axisLabelVisible: true,
            title: "",
          })
        );
      }
    });

    // --- Kullanıcının kendi formülleri (ayrı panel) ---
    aktifOzelAltPaneller.forEach((f) => {
      const veri = ozelFormulVeri[f.id];
      if (!veri || !veri.available) return;
      const pane = chart.addPane();
      pane.setHeight(ALT_YUKSEKLIK);
      const paneIndex = pane.paneIndex();
      const zamanlar = veri.dates.map((d) => toChartTime(d));
      const noktalar = zamanlar
        .map((t, i) => ({ time: t as any, value: veri.values[i] }))
        .filter((p): p is { time: any; value: number } => p.value !== null && p.value !== undefined);
      const s = chart.addSeries(LineSeries, { color: f.renk, lineWidth: 2, priceLineVisible: false }, paneIndex);
      s.setData(noktalar);
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
    // NOT: aktifOzelOverlaylar/aktifOzelAltPaneller BİLEREK bağımlılığa
    // eklenmedi -- bunlar her render'da yeniden hesaplanan (.filter() ile
    // üretilen) diziler, yani referansları her render'da değişir. Bunları
    // bağımlılığa koymak "efekt çalışır -> setState -> yeniden render ->
    // yeni dizi referansı -> efekt tekrar çalışır" sonsuz döngüsüne yol
    // açıyordu (ölçüldü: "Maximum update depth exceeded"). Bunun yerine
    // KAYNAK state olan `ozelFormuller`e bağımlı olunur -- o yalnızca
    // gerçekten değiştiğinde (formül eklenip/silinip/açılıp kapatıldığında)
    // yeni referans alır.
  }, [data, symbol, baseline, tercih, indicatorData, gostergeDesteklenir, ozelFormulVeri, ozelFormuller]);

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
  const secimSayisi = tercih.overlays.length + tercih.subpanes.length + ozelFormuller.filter((f) => f.aktif).length;

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
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-semibold border transition ${
              secimSayisi > 0
                ? "bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]"
                : "bg-[#0B0E14] border-[#242B35] text-gray-400 hover:text-white"
            }`}
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
        <div ref={chartContainerRef} className="w-full" style={{ height: 320 + toplamAltPanelSayisi * 110 }} />
      </div>

      {pickerOpen && gostergeDesteklenir && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setPickerOpen(false)}
        >
          <div
            className="relative w-full sm:max-w-md bg-[#151921] border border-[#242B35] rounded-t-2xl sm:rounded-2xl max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Mobilde alttan açılan sheet'i elle sürükleyip kapatma hissi veren tutamaç. */}
            <div className="sm:hidden flex justify-center pt-2.5 pb-1 shrink-0">
              <div className="w-9 h-1 rounded-full bg-[#242B35]" />
            </div>

            <div className="shrink-0 px-4 pb-3 pt-1 sm:pt-4 flex items-center justify-between border-b border-[#242B35]">
              <div>
                <h3 className="text-sm font-bold text-white">Grafik Göstergeleri</h3>
                <p className="text-[10px] text-gray-500 mt-0.5">Fiyatın üstüne veya altına ekle</p>
              </div>
              <div className="flex items-center gap-1">
                {secimSayisi > 0 && (
                  <button
                    onClick={sifirlaGostergeler}
                    className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[10px] font-semibold text-gray-500 hover:text-white hover:bg-[#0B0E14] transition"
                    title="Tümünü kaldır"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Sıfırla
                  </button>
                )}
                <button
                  onClick={() => setPickerOpen(false)}
                  className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-[#0B0E14] transition"
                  title="Kapat"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="overflow-y-auto p-4 space-y-5">
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Layers className="w-3 h-3 text-gray-600" />
                  <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">Fiyat üzerine bindirilir</p>
                </div>
                <div className="space-y-1.5">
                  {OVERLAY_TANIM.map((o) => {
                    const secili = tercih.overlays.includes(o.key);
                    const Icon = o.icon;
                    return (
                      <button
                        key={o.key}
                        onClick={() => toggleOverlay(o.key)}
                        className={`w-full flex items-center gap-3 p-2.5 rounded-xl text-left transition border-l-[3px] ${
                          secili ? "bg-[#0B0E14]" : "border-l-transparent hover:bg-[#0B0E14]/60"
                        }`}
                        style={{ borderLeftColor: secili ? o.renk : "transparent" }}
                      >
                        <span
                          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                          style={{ backgroundColor: `${o.renk}1A`, color: o.renk }}
                        >
                          <Icon className="w-4 h-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-xs font-semibold text-white">{o.label}</span>
                          <span className="block text-[10px] text-gray-500 truncate">{o.aciklama}</span>
                        </span>
                        {secili && <Check className="w-4 h-4 shrink-0" style={{ color: o.renk }} />}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <PanelBottom className="w-3 h-3 text-gray-600" />
                    <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">Alt panel</p>
                  </div>
                  <p className="text-[10px] font-semibold text-gray-600 tabular-nums">
                    {toplamAltPanelSayisi}/{MAKS_ALT_PANEL} seçili
                  </p>
                </div>
                <div className="space-y-1.5">
                  {SUBPANE_TANIM.map((s) => {
                    const secili = tercih.subpanes.includes(s.key);
                    const devreDisi = !secili && toplamAltPanelSayisi >= MAKS_ALT_PANEL;
                    const Icon = s.icon;
                    const renk = "#10B981";
                    return (
                      <button
                        key={s.key}
                        onClick={() => toggleSubpane(s.key)}
                        disabled={devreDisi}
                        className={`w-full flex items-center gap-3 p-2.5 rounded-xl text-left transition border-l-[3px] ${
                          secili
                            ? "bg-[#0B0E14]"
                            : devreDisi
                            ? "border-l-transparent opacity-40 cursor-not-allowed"
                            : "border-l-transparent hover:bg-[#0B0E14]/60"
                        }`}
                        style={{ borderLeftColor: secili ? renk : "transparent" }}
                      >
                        <span
                          className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                            secili ? "" : "bg-[#0B0E14] text-gray-500"
                          }`}
                          style={secili ? { backgroundColor: `${renk}1A`, color: renk } : undefined}
                        >
                          <Icon className="w-4 h-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className={`block text-xs font-semibold ${secili ? "text-white" : "text-gray-300"}`}>{s.label}</span>
                          <span className="block text-[10px] text-gray-500 truncate">{s.aciklama}</span>
                        </span>
                        {secili && <Check className="w-4 h-4 shrink-0" style={{ color: renk }} />}
                      </button>
                    );
                  })}
                </div>
                <p className="text-[10px] text-gray-600 mt-2.5 px-0.5">
                  Küçük ekranda okunabilirlik için aynı anda en fazla {MAKS_ALT_PANEL} alt panel açılabilir.
                </p>
              </div>

              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <FunctionSquare className="w-3 h-3 text-gray-600" />
                  <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">Kendi Formülün</p>
                </div>

                {ozelFormuller.length > 0 && (
                  <div className="space-y-1.5 mb-2.5">
                    {ozelFormuller.map((f) => (
                      <div
                        key={f.id}
                        className="w-full flex items-center gap-3 p-2.5 rounded-xl border-l-[3px] bg-[#0B0E14]"
                        style={{ borderLeftColor: f.aktif ? f.renk : "transparent" }}
                      >
                        <button
                          onClick={() => formulAcKapat(f.id)}
                          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                          style={{ backgroundColor: `${f.renk}1A`, color: f.renk }}
                          title={f.aktif ? "Devre dışı bırak" : "Etkinleştir"}
                        >
                          <FunctionSquare className="w-4 h-4" />
                        </button>
                        <button onClick={() => formulAcKapat(f.id)} className="min-w-0 flex-1 text-left">
                          <span className={`block text-xs font-mono font-semibold truncate ${f.aktif ? "text-white" : "text-gray-500"}`}>
                            {f.formula}
                          </span>
                          <span className="block text-[10px] text-gray-500">{f.hedef === "overlay" ? "Fiyat üzerine" : "Ayrı panel"}</span>
                        </button>
                        <button
                          onClick={() => formulSil(f.id)}
                          className="p-1.5 text-gray-600 hover:text-[#F43F5E] transition shrink-0"
                          title="Sil"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {ozelFormuller.length < MAKS_OZEL_FORMUL ? (
                  <div className="bg-[#0B0E14] border border-[#242B35] rounded-xl p-3 space-y-2.5">
                    <input
                      value={formulMetni}
                      onChange={(e) => {
                        setFormulMetni(e.target.value);
                        setFormulHata(null);
                      }}
                      placeholder="ör. close - sma(20)"
                      className="w-full bg-transparent border border-[#242B35] rounded-lg px-3 py-2 text-xs font-mono text-white placeholder:text-gray-600 outline-none focus:border-[#10B981]/50"
                    />
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => setFormulHedef("overlay")}
                        className={`flex-1 px-2 py-1.5 rounded-lg text-[10px] font-semibold transition ${
                          formulHedef === "overlay" ? "bg-[#10B981] text-[#0B0E14]" : "bg-[#151921] text-gray-400"
                        }`}
                      >
                        Fiyat üzerine
                      </button>
                      <button
                        onClick={() => setFormulHedef("subpane")}
                        className={`flex-1 px-2 py-1.5 rounded-lg text-[10px] font-semibold transition ${
                          formulHedef === "subpane" ? "bg-[#10B981] text-[#0B0E14]" : "bg-[#151921] text-gray-400"
                        }`}
                      >
                        Ayrı panel
                      </button>
                      <button
                        onClick={formulEkle}
                        disabled={formulYukleniyor || !formulMetni.trim()}
                        className="px-3 py-1.5 rounded-lg text-[10px] font-bold bg-[#10B981] text-[#0B0E14] disabled:opacity-40 transition shrink-0"
                      >
                        {formulYukleniyor ? "..." : "Ekle"}
                      </button>
                    </div>
                    {formulHata && <p className="text-[10px] text-[#F43F5E]">{formulHata}</p>}
                    <p className="text-[10px] text-gray-600">
                      Değişkenler: open, high, low, close, volume · Fonksiyonlar: sma(n), ema(n), rsi(n), abs(x), min(a,b), max(a,b)
                    </p>
                  </div>
                ) : (
                  <p className="text-[10px] text-gray-600 px-0.5">En fazla {MAKS_OZEL_FORMUL} özel formül kaydedebilirsiniz.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
