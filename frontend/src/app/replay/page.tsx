"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart, ColorType, CandlestickSeries, createSeriesMarkers,
  type ISeriesApi, type ISeriesMarkersPluginApi, type IChartApi,
} from "lightweight-charts";
import {
  History, Search, Play, Pause, RotateCcw, ArrowLeft, TrendingUp, TrendingDown,
} from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface StockSearchResult {
  symbol: string;
  company_name: string;
}

interface Bar {
  time: number;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

const UP = "#10B981";
const DOWN = "#F43F5E";
const BASLANGIC_BAKIYE = 100000;

// TradingViewChart.tsx'teki toChartTime ile AYNI mantık: lightweight-charts
// zaman etiketlerini UTC render eder, offset kaydırılmazsa TR'de 3 saat kayar.
// İki bileşen aynı veriyi farklı yorumlamasın diye burada da birebir kopyalandı.
function toChartTime(iso: string): number {
  const d = new Date(iso);
  return Math.floor((d.getTime() - d.getTimezoneOffset() * 60_000) / 1000);
}

const SPEED_MS: Record<number, number> = { 1: 700, 2: 350, 5: 130 };

interface Islem {
  tarih: string;
  tur: "AL" | "SAT";
  adet: number;
  fiyat: number;
}

export default function ReplayPage() {
  const { token, loading: authLoading } = useAuth();

  const [step, setStep] = useState<"setup" | "playing">("setup");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [symbol, setSymbol] = useState<string | null>(null);
  const [rangeCode, setRangeCode] = useState<"1Y" | "5Y">("5Y");
  const [allBars, setAllBars] = useState<Bar[]>([]);
  const [startIndex, setStartIndex] = useState(0);
  const [loadingData, setLoadingData] = useState(false);
  const [setupError, setSetupError] = useState("");

  const [revealedCount, setRevealedCount] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<1 | 2 | 5>(1);

  const [nakit, setNakit] = useState(BASLANGIC_BAKIYE);
  const [pozAdet, setPozAdet] = useState(0);
  const [pozMaliyet, setPozMaliyet] = useState(0);
  const [islemler, setIslemler] = useState<Islem[]>([]);
  const [adetInput, setAdetInput] = useState("10");

  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const markersRef = useRef<ISeriesMarkersPluginApi<any> | null>(null);

  // --- Sembol arama ---
  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks/search?q=${encodeURIComponent(query)}`);
        if (res.ok && !cancelled) setResults((await res.json()).slice(0, 8));
      } catch {
        // arama başarısız olursa sessizce boş liste kalır
      }
    }, 250);
    return () => { cancelled = true; clearTimeout(t); };
  }, [query]);

  const secSembol = async (s: string, r: "1Y" | "5Y" = rangeCode) => {
    setSymbol(s);
    setQuery(s);
    setResults([]);
    setSetupError("");
    setLoadingData(true);
    try {
      const res = await fetch(`${API_BASE}/stocks/${s}/history?range=${r}`);
      if (!res.ok) throw new Error();
      const raw: { recorded_at: string; open: number | null; high: number | null; low: number | null; price: number }[] = await res.json();
      const bars: Bar[] = raw
        .filter((r2) => r2.open !== null && r2.high !== null && r2.low !== null)
        .map((r2) => ({
          time: toChartTime(r2.recorded_at),
          date: r2.recorded_at.slice(0, 10),
          open: r2.open as number,
          high: r2.high as number,
          low: r2.low as number,
          close: r2.price,
        }));
      if (bars.length < 40) {
        setSetupError("Bu hisse için yeterli günlük geçmiş veri yok (en az 40 gün gerekir).");
        setAllBars([]);
        return;
      }
      setAllBars(bars);
      setStartIndex(Math.floor(bars.length * 0.5));
    } catch {
      setSetupError("Hisse verisi alınamadı. Sembolü kontrol edin.");
      setAllBars([]);
    } finally {
      setLoadingData(false);
    }
  };

  const baslat = () => {
    setRevealedCount(startIndex);
    setNakit(BASLANGIC_BAKIYE);
    setPozAdet(0);
    setPozMaliyet(0);
    setIslemler([]);
    setPlaying(false);
    setStep("playing");
  };

  const baseDegis = () => {
    setPlaying(false);
    setStep("setup");
  };

  // --- Grafik oluşturma (yalnızca "playing" adımına girildiğinde) ---
  useEffect(() => {
    if (step !== "playing" || !containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#9ca3af" },
      grid: { vertLines: { color: "rgba(55,65,81,0.2)" }, horzLines: { color: "rgba(55,65,81,0.2)" } },
      width: containerRef.current.clientWidth,
      height: 380,
      timeScale: { timeVisible: false, borderVisible: false },
      rightPriceScale: { borderVisible: false },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: UP, downColor: DOWN, borderVisible: false, wickUpColor: UP, wickDownColor: DOWN,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    const markers = createSeriesMarkers(series, []);

    chartRef.current = chart;
    seriesRef.current = series;
    markersRef.current = markers;

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      markersRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, symbol]);

  // --- Görünen bar sayısı değiştikçe grafiği güncelle ---
  useEffect(() => {
    if (!seriesRef.current || revealedCount === 0) return;
    seriesRef.current.setData(
      allBars.slice(0, revealedCount).map((b) => ({ ...b, time: b.time as any }))
    );
    chartRef.current?.timeScale().fitContent();
  }, [revealedCount, allBars]);

  // --- Oynatma döngüsü ---
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setRevealedCount((c) => {
        if (c >= allBars.length) {
          setPlaying(false);
          return c;
        }
        return c + 1;
      });
    }, SPEED_MS[speed]);
    return () => clearInterval(id);
  }, [playing, speed, allBars.length]);

  const currentBar = revealedCount > 0 ? allBars[revealedCount - 1] : null;
  const bitti = revealedCount >= allBars.length;

  const guncelleMarkers = useCallback((yeniIslemler: Islem[]) => {
    if (!markersRef.current) return;
    markersRef.current.setMarkers(
      yeniIslemler.map((i) => ({
        time: toChartTime(i.tarih) as any,
        position: i.tur === "AL" ? "belowBar" : "aboveBar",
        color: i.tur === "AL" ? UP : DOWN,
        shape: i.tur === "AL" ? "arrowUp" : "arrowDown",
        text: `${i.tur} ${i.adet}`,
      }))
    );
  }, []);

  const adet = Number.parseFloat(adetInput);
  const adetGecerli = Number.isFinite(adet) && adet > 0;

  const handleAl = () => {
    if (!currentBar || !adetGecerli) return;
    const maliyet = adet * currentBar.close;
    if (maliyet > nakit) return;
    setNakit((n) => n - maliyet);
    setPozMaliyet((eski) => (pozAdet + adet > 0 ? ((pozAdet * eski) + maliyet) / (pozAdet + adet) : 0));
    setPozAdet((p) => p + adet);
    const yeni = [...islemler, { tarih: currentBar.date, tur: "AL" as const, adet, fiyat: currentBar.close }];
    setIslemler(yeni);
    guncelleMarkers(yeni);
  };

  const handleSat = () => {
    if (!currentBar || !adetGecerli || adet > pozAdet) return;
    setNakit((n) => n + adet * currentBar.close);
    setPozAdet((p) => p - adet);
    const yeni = [...islemler, { tarih: currentBar.date, tur: "SAT" as const, adet, fiyat: currentBar.close }];
    setIslemler(yeni);
    guncelleMarkers(yeni);
  };

  const toplamDeger = nakit + pozAdet * (currentBar?.close ?? 0);
  const getiriPct = ((toplamDeger - BASLANGIC_BAKIYE) / BASLANGIC_BAKIYE) * 100;

  if (authLoading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <p className="text-gray-400 text-sm">Yükleniyor...</p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 text-center">
          <p className="text-xs text-gray-400">Replay modunu kullanmak için giriş yapmalısınız.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-5">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <History className="w-5 h-5 text-[#F59E0B]" /> Replay Modu
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Geçmiş bir tarihe git, grafiği gün gün (hızlandırılmış) izleyerek pratik al-sat
          yap. Tamamen hayali bir pratik alanıdır — gerçek bakiyeni/portföyünü ETKİLEMEZ,
          sayfadan çıkınca sıfırlanır.
        </p>
      </div>

      {step === "setup" ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-4">
          <div className="relative">
            <label className="block text-[11px] font-semibold text-gray-400 mb-1.5">Hisse Seç</label>
            <div className="relative">
              <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                value={query}
                onChange={(e) => { setQuery(e.target.value); setSymbol(null); setAllBars([]); }}
                placeholder="Örn. THYAO, SASA..."
                className="w-full min-h-[44px] pl-9 pr-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm focus:outline-none focus:border-[#F59E0B]"
              />
            </div>
            {results.length > 0 && (
              <div className="absolute z-10 mt-1 w-full bg-[#0B0E14] border border-[#242B35] rounded-lg overflow-hidden shadow-none">
                {results.map((r) => (
                  <button
                    key={r.symbol}
                    onClick={() => secSembol(r.symbol)}
                    className="w-full text-left px-3 py-2.5 min-h-[44px] text-xs text-gray-200 hover:bg-[#151921] transition border-b border-[#242B35] last:border-0"
                  >
                    <span className="font-bold text-white">{r.symbol}</span>
                    <span className="text-gray-500 ml-2">{r.company_name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {symbol && (
            <>
              <div className="flex items-center gap-1 bg-[#0B0E14] border border-[#242B35] rounded-lg p-1 w-fit">
                {(["1Y", "5Y"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => secSembol(symbol, r)}
                    className={`px-4 min-h-[36px] text-[11px] font-semibold rounded-md transition ${
                      rangeCode === r ? "bg-[#242B35] text-white" : "text-gray-500 hover:text-gray-300"
                    }`}
                  >
                    {r === "1Y" ? "Son 1 Yıl" : "Son 5 Yıl"}
                  </button>
                ))}
              </div>

              {loadingData && <p className="text-xs text-gray-500">Veri yükleniyor...</p>}
              {setupError && <p className="text-xs text-[#F43F5E]">{setupError}</p>}

              {allBars.length > 0 && (
                <div>
                  <label className="block text-[11px] font-semibold text-gray-400 mb-1.5">
                    Başlangıç Noktası — <span className="text-white">{allBars[startIndex]?.date}</span>
                  </label>
                  <input
                    type="range"
                    min={30}
                    max={allBars.length - 2}
                    value={startIndex}
                    onChange={(e) => setStartIndex(Number(e.target.value))}
                    className="w-full accent-[#F59E0B]"
                  />
                  <div className="flex justify-between text-[10px] text-gray-600 mt-1">
                    <span>{allBars[30]?.date}</span>
                    <span>{allBars[allBars.length - 2]?.date}</span>
                  </div>

                  <button
                    onClick={baslat}
                    className="w-full mt-4 min-h-[44px] rounded-lg bg-[#10B981] hover:bg-[#0FA271] text-[#0B0E14] text-sm font-bold transition"
                  >
                    Replay&apos;i Başlat
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <button onClick={baseDegis} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition min-h-[36px]">
              <ArrowLeft className="w-3.5 h-3.5" /> Farklı hisse/tarih seç
            </button>
            <span className="text-xs text-gray-500 tabular-nums">
              Gün {revealedCount - startIndex} / {allBars.length - startIndex}
              {currentBar && <span className="text-white font-semibold ml-2">{currentBar.date}</span>}
            </span>
          </div>

          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
            <div ref={containerRef} className="w-full" />
          </div>

          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex flex-wrap items-center gap-3">
            <button
              onClick={() => setPlaying((p) => !p)}
              disabled={bitti}
              className="min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg bg-[#242B35] hover:bg-[#2E3641] disabled:opacity-40 text-white transition"
              aria-label={playing ? "Duraklat" : "Oynat"}
            >
              {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
            <div className="flex items-center gap-1 bg-[#0B0E14] border border-[#242B35] rounded-lg p-1">
              {([1, 2, 5] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-3 min-h-[36px] text-[11px] font-semibold rounded-md transition ${
                    speed === s ? "bg-[#242B35] text-white" : "text-gray-500 hover:text-gray-300"
                  }`}
                >
                  {s}x
                </button>
              ))}
            </div>
            <button
              onClick={baslat}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition min-h-[36px] ml-auto"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Yeniden başlat
            </button>
          </div>

          {bitti && (
            <div className={`rounded-xl p-4 text-center ${getiriPct >= 0 ? "bg-[#10B981]/10 border border-[#10B981]/30" : "bg-[#F43F5E]/10 border border-[#F43F5E]/30"}`}>
              <p className="text-sm font-bold text-white">Replay tamamlandı</p>
              <p className={`text-lg font-bold tabular-nums ${getiriPct >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"}`}>
                {getiriPct > 0 ? "+" : ""}{getiriPct.toFixed(2)}%
              </p>
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
              <p className="text-[10px] text-gray-500 uppercase font-semibold">Nakit</p>
              <p className="text-sm font-bold text-white tabular-nums">{nakit.toLocaleString("tr-TR", { maximumFractionDigits: 0 })} TL</p>
            </div>
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
              <p className="text-[10px] text-gray-500 uppercase font-semibold">Pozisyon</p>
              <p className="text-sm font-bold text-white tabular-nums">{pozAdet.toLocaleString("tr-TR")} adet</p>
            </div>
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
              <p className="text-[10px] text-gray-500 uppercase font-semibold">Toplam Değer</p>
              <p className="text-sm font-bold text-white tabular-nums">{toplamDeger.toLocaleString("tr-TR", { maximumFractionDigits: 0 })} TL</p>
            </div>
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
              <p className="text-[10px] text-gray-500 uppercase font-semibold">Getiri</p>
              <p className={`text-sm font-bold tabular-nums ${getiriPct >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"}`}>
                {getiriPct > 0 ? "+" : ""}{getiriPct.toFixed(2)}%
              </p>
            </div>
          </div>

          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
            <p className="text-[11px] font-semibold text-gray-400 mb-2">
              {currentBar ? `Güncel fiyat: ${currentBar.close.toLocaleString("tr-TR")} TL` : "—"}
            </p>
            <div className="flex gap-2">
              <input
                type="number"
                inputMode="decimal"
                min={1}
                value={adetInput}
                onChange={(e) => setAdetInput(e.target.value)}
                // min-w-0 ZORUNLU: flex item'lar varsayılan olarak min-width:auto
                // alır, yani içeriği kadar büzülmeden küçülmez -- bu da dar
                // ekranda (mobil) yanındaki AL/SAT butonlarını ekran dışına iter.
                className="flex-1 min-w-0 min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm tabular-nums focus:outline-none focus:border-[#F59E0B]"
              />
              <button
                onClick={handleAl}
                disabled={!adetGecerli || !currentBar || adet * currentBar.close > nakit}
                className="shrink-0 min-w-[64px] min-h-[44px] px-2 rounded-lg bg-[#10B981] hover:bg-[#0FA271] disabled:opacity-40 text-[#0B0E14] text-xs font-bold transition flex items-center justify-center gap-1"
              >
                <TrendingUp className="w-3.5 h-3.5" /> AL
              </button>
              <button
                onClick={handleSat}
                disabled={!adetGecerli || adet > pozAdet}
                className="shrink-0 min-w-[64px] min-h-[44px] px-2 rounded-lg bg-[#F43F5E] hover:bg-[#DC2F4C] disabled:opacity-40 text-white text-xs font-bold transition flex items-center justify-center gap-1"
              >
                <TrendingDown className="w-3.5 h-3.5" /> SAT
              </button>
            </div>
          </div>

          {islemler.length > 0 && (
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
              <p className="text-[11px] font-semibold text-gray-400 mb-2">İşlem Geçmişi (bu oturum)</p>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {[...islemler].reverse().map((i, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs">
                    <span className={i.tur === "AL" ? "text-[#10B981] font-semibold" : "text-[#F43F5E] font-semibold"}>
                      {i.tur} {i.adet}
                    </span>
                    <span className="text-gray-500 tabular-nums">{i.fiyat.toLocaleString("tr-TR")} TL</span>
                    <span className="text-gray-600">{i.tarih}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
