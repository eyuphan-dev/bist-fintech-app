"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FlaskConical, RefreshCw, Info, TrendingUp, TrendingDown } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Point {
  date: string;
  strategy: number;
  buy_hold: number;
}

interface Trade {
  date: string;
  action: string;
  price: number;
  pnl_pct: number | null;
}

interface Result {
  ok: boolean;
  error?: string | null;
  strategy_label?: string;
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
  final_value?: number;
  strategy_return_pct?: number;
  buy_hold_return_pct?: number;
  excess_return_pct?: number;
  trade_count?: number;
  closed_trades?: number;
  win_rate?: number | null;
  max_drawdown_pct?: number;
  buy_hold_max_drawdown_pct?: number;
  commission_pct?: number;
  in_position?: boolean;
  equity_curve?: Point[];
  trades?: Trade[];
}

const STRATEJILER = [
  { key: "SMA_CROSS", label: "Ortalama Kesişimi" },
  { key: "RSI", label: "RSI" },
  { key: "MACD", label: "MACD" },
];
const YILLAR = [1, 3, 5];

const pct = (v: number | undefined | null) =>
  v === undefined || v === null ? "—" : `${v >= 0 ? "+" : "−"}%${Math.abs(v).toLocaleString("tr-TR", { maximumFractionDigits: 1 })}`;

/** İki serili özkaynak eğrisi. Ölçek logaritmik değil; uzun vadede fark abartılı görünmesin diye ortak eksen kullanılır. */
function Egri({ points }: { points: Point[] }) {
  if (points.length < 2) return null;
  const W = 300, H = 90;
  const tum = points.flatMap((p) => [p.strategy, p.buy_hold]);
  const min = Math.min(...tum), max = Math.max(...tum);
  const aralik = max - min || 1;
  const x = (i: number) => (i / (points.length - 1)) * W;
  const y = (v: number) => H - ((v - min) / aralik) * (H - 6) - 3;
  const yol = (sec: (p: Point) => number) =>
    points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(sec(p)).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-24" preserveAspectRatio="none">
      <path d={yol((p) => p.buy_hold)} fill="none" stroke="#8A99AD" strokeWidth="1" vectorEffect="non-scaling-stroke" />
      <path d={yol((p) => p.strategy)} fill="none" stroke="#4A87C7" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/**
 * Strateji geri testi.
 *
 * Ücretli platformlarda (Matriks Prime, Fintables) paket içinde olan özellik.
 * Veri zaten bizde: 2021'den bu yana günlük OHLCV.
 *
 * Sonuç ekranında al-tut karşılaştırması ÖNE ÇIKARILIR: "%376 kazandırdı" tek
 * başına anlamsızdır, aynı dönemde hisse %994 yükseldiyse strateji aslında
 * kaybettirmiştir. Kullanıcının görmesi gereken sayı farktır.
 */
export default function BacktestPanel({ symbol }: { symbol: string }) {
  const { token } = useAuth();
  const [strategy, setStrategy] = useState("SMA_CROSS");
  const [years, setYears] = useState(3);
  const [data, setData] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/stocks/${symbol}/backtest?strategy=${strategy}&years=${years}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) setData(await res.json());
      else if (res.status === 429) setData({ ok: false, error: "Çok hızlı deniyorsunuz, biraz bekleyin." });
      else setData({ ok: false, error: "Geri test çalıştırılamadı." });
    } catch {
      setData({ ok: false, error: "Geri test çalıştırılamadı." });
    } finally {
      setLoading(false);
    }
  }, [token, symbol, strategy, years]);

  useEffect(() => { load(); }, [load]);

  const kazandi = (data?.excess_return_pct ?? 0) > 0;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <FlaskConical className="w-4 h-4 text-[#F59E0B]" />
        <h4 className="text-xs font-bold text-white uppercase tracking-wide">Strateji Geri Testi</h4>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {STRATEJILER.map((s) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setStrategy(s.key)}
            className={`px-2.5 min-h-[32px] rounded-lg text-[11px] font-semibold transition ${
              strategy === s.key ? "bg-[#4A87C7] text-[#0B0E14]" : "bg-[#0B0E14] text-gray-400 hover:text-white"
            }`}
          >
            {s.label}
          </button>
        ))}
        <span className="w-px bg-[#242B35] mx-1" />
        {YILLAR.map((y) => (
          <button
            key={y}
            type="button"
            onClick={() => setYears(y)}
            className={`px-2.5 min-h-[32px] rounded-lg text-[11px] font-semibold tabular-nums transition ${
              years === y ? "bg-[#4A87C7] text-[#0B0E14]" : "bg-[#0B0E14] text-gray-400 hover:text-white"
            }`}
          >
            {y} yıl
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 py-6 justify-center text-gray-500">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span className="text-[11px]">Hesaplanıyor...</span>
        </div>
      ) : !data ? null : !data.ok ? (
        <p className="text-[11px] text-gray-500 py-3">{data.error}</p>
      ) : (
        <>
          {/* En önemli sayı: farkın kendisi. */}
          <div
            className="rounded-xl p-3 border"
            style={{
              backgroundColor: kazandi ? "rgba(16,185,129,0.06)" : "rgba(244,63,94,0.06)",
              borderColor: kazandi ? "rgba(16,185,129,0.25)" : "rgba(244,63,94,0.25)",
            }}
          >
            <div className="flex items-center gap-1.5">
              {kazandi ? (
                <TrendingUp className="w-3.5 h-3.5 text-[#10B981]" />
              ) : (
                <TrendingDown className="w-3.5 h-3.5 text-[#F43F5E]" />
              )}
              <p className="text-[11px] font-bold" style={{ color: kazandi ? "#10B981" : "#F43F5E" }}>
                {kazandi ? "Al-tut stratejisini geçti" : "Al-tut stratejisinin gerisinde kaldı"}
              </p>
            </div>
            <p className="text-[10px] text-gray-400 mt-1 leading-relaxed">
              Strateji <strong className="text-gray-200">{pct(data.strategy_return_pct)}</strong>, hisseyi alıp
              hiç dokunmamak <strong className="text-gray-200">{pct(data.buy_hold_return_pct)}</strong> getirirdi.
              Fark <strong style={{ color: kazandi ? "#10B981" : "#F43F5E" }}>{pct(data.excess_return_pct)}</strong>.
            </p>
          </div>

          <div className="space-y-1">
            <Egri points={data.equity_curve ?? []} />
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="flex items-center gap-1 text-[9px] text-gray-500">
                  <span className="w-2.5 h-0.5 bg-[#4A87C7]" /> Strateji
                </span>
                <span className="flex items-center gap-1 text-[9px] text-gray-500">
                  <span className="w-2.5 h-px bg-[#8A99AD]" /> Al ve tut
                </span>
              </div>
              <span className="text-[9px] text-gray-600 tabular-nums">
                {data.start_date} → {data.end_date}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            {[
              { l: "İşlem", v: String(data.trade_count ?? 0) },
              { l: "İsabet", v: data.win_rate !== null && data.win_rate !== undefined ? `%${data.win_rate}` : "—" },
              { l: "Maks. Düşüş", v: pct(data.max_drawdown_pct) },
            ].map((k) => (
              <div key={k.l} className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-2">
                <p className="text-[9px] text-gray-500 uppercase font-bold">{k.l}</p>
                <p className="text-xs font-bold text-white tabular-nums mt-0.5">{k.v}</p>
              </div>
            ))}
          </div>

          <p className="text-[9px] text-gray-600 leading-relaxed flex items-start gap-1.5 border-t border-[#242B35] pt-2.5">
            <Info className="w-3 h-3 shrink-0 mt-0.5" />
            <span>
              Sinyal günün kapanışıyla hesaplanır, işlem <strong>ertesi günün açılışında</strong> yapılır —
              sinyalin oluştuğu mumdan alım varsaymak gerçekte mümkün olmayan bir fiyattan işlem
              yapmak olurdu. Komisyon %{data.commission_pct} olarak her alım ve satımda düşülür.
              Geçmiş performans geleceği göstermez; bu bir simülasyondur, yatırım tavsiyesi değildir.
            </span>
          </p>
        </>
      )}
    </div>
  );
}
