"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Trophy, Target, Clock, TrendingUp, TrendingDown, Info } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Trade {
  symbol: string;
  pnl: number;
  pnl_pct: number | null;
  date: string | null;
}

interface StockRow {
  symbol: string;
  pnl: number;
  trades: number;
}

interface Data {
  has_data: boolean;
  years: number[];
  year: number | null;
  realized_pnl?: number | null;
  sell_count?: number | null;
  win_count?: number | null;
  loss_count?: number | null;
  win_rate?: number | null;
  avg_holding_days?: number | null;
  matched_sells?: number | null;
  best_trade?: Trade | null;
  worst_trade?: Trade | null;
  by_stock?: StockRow[];
}

const tl = (v: number) =>
  `${v >= 0 ? "+" : "−"}${Math.abs(v).toLocaleString("tr-TR", { maximumFractionDigits: 0 })} TL`;

function Kutu({
  label,
  value,
  hint,
  color,
  Icon,
}: {
  label: string;
  value: string;
  hint?: string;
  color?: string;
  Icon: React.ElementType;
}) {
  return (
    <div className="bg-[#0B0E14] border border-[#242B35] rounded-xl p-3">
      <div className="flex items-center gap-1.5 mb-1">
        <Icon className="w-3 h-3 text-gray-500" strokeWidth={1.5} />
        <p className="text-[9px] text-gray-500 uppercase font-bold tracking-wide">{label}</p>
      </div>
      <p className="text-base font-bold tabular-nums" style={color ? { color } : undefined}>
        {value}
      </p>
      {hint && <p className="text-[9px] text-gray-600 mt-0.5 leading-snug">{hint}</p>}
    </div>
  );
}

/**
 * İşlem performans karnesi.
 *
 * İşlem geçmişi zaten listeleniyordu ama 40 satırlık bir listeye bakıp
 * "iyi mi gidiyorum" sorusunu cevaplamak mümkün değil. Burada aynı kayıtlar
 * özetlenir: gerçekleşen kâr/zarar, isabet oranı, ortalama tutma süresi ve
 * hangi hissede kazanıp hangisinde kaybedildiği.
 */
export default function PerformanceScorecard() {
  const { token } = useAuth();
  const [data, setData] = useState<Data | null>(null);
  const [year, setYear] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const url = year ? `${API_BASE}/portfolio/scorecard?year=${year}` : `${API_BASE}/portfolio/scorecard`;
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("Karne alınamadı:", err);
    }
  }, [token, year]);

  useEffect(() => {
    load();
  }, [load]);

  if (!data || !data.has_data) return null;

  const pnl = data.realized_pnl ?? 0;
  const pnlRenk = pnl > 0 ? "#10B981" : pnl < 0 ? "#F43F5E" : "#8A99AD";
  const kapali = (data.win_count ?? 0) + (data.loss_count ?? 0);

  const kazananlar = (data.by_stock ?? []).filter((s) => s.pnl > 0);
  const kaybettirenler = (data.by_stock ?? []).filter((s) => s.pnl < 0).reverse();
  const enBuyuk = Math.max(1, ...(data.by_stock ?? []).map((s) => Math.abs(s.pnl)));

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <Trophy className="w-4 h-4 text-[#F59E0B]" />
          <h2 className="text-sm font-bold text-white">Performans Karnem</h2>
        </div>
        {data.years.length > 1 && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setYear(null)}
              className={`px-2.5 min-h-[32px] rounded-lg text-[11px] font-semibold transition ${
                year === null ? "bg-[#10B981] text-[#0B0E14]" : "text-gray-400 hover:text-white"
              }`}
            >
              Tümü
            </button>
            {data.years.map((y) => (
              <button
                key={y}
                type="button"
                onClick={() => setYear(y)}
                className={`px-2.5 min-h-[32px] rounded-lg text-[11px] font-semibold tabular-nums transition ${
                  year === y ? "bg-[#10B981] text-[#0B0E14]" : "text-gray-400 hover:text-white"
                }`}
              >
                {y}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5">
        <Kutu
          label="Gerçekleşen K/Z"
          value={tl(pnl)}
          color={pnlRenk}
          hint={`${data.sell_count ?? 0} satış işleminden`}
          Icon={pnl >= 0 ? TrendingUp : TrendingDown}
        />
        <Kutu
          label="İsabet Oranı"
          value={data.win_rate !== null && data.win_rate !== undefined ? `%${data.win_rate}` : "—"}
          hint={kapali ? `${data.win_count} kârlı / ${data.loss_count} zararlı` : "Henüz kapanan işlem yok"}
          Icon={Target}
        />
        <Kutu
          label="Ort. Tutma Süresi"
          value={data.avg_holding_days !== null && data.avg_holding_days !== undefined
            ? `${data.avg_holding_days} gün`
            : "—"}
          hint={
            data.matched_sells !== undefined && data.matched_sells !== null && data.matched_sells < (data.sell_count ?? 0)
              ? `${data.matched_sells} satış eşleşti`
              : undefined
          }
          Icon={Clock}
        />
        <Kutu
          label="En İyi İşlem"
          value={data.best_trade ? tl(data.best_trade.pnl) : "—"}
          color={data.best_trade && data.best_trade.pnl > 0 ? "#10B981" : undefined}
          hint={
            data.best_trade
              ? `${data.best_trade.symbol}${data.best_trade.pnl_pct !== null ? ` · %${data.best_trade.pnl_pct}` : ""}`
              : undefined
          }
          Icon={Trophy}
        />
      </div>

      {(kazananlar.length > 0 || kaybettirenler.length > 0) && (
        <div className="space-y-1.5 pt-1">
          <p className="text-[9px] text-gray-500 uppercase font-bold">Hisse Bazında</p>
          {[...kazananlar, ...kaybettirenler].map((s) => {
            const pozitif = s.pnl >= 0;
            return (
              <div key={s.symbol} className="flex items-center gap-2">
                <span className="text-[11px] font-bold text-gray-300 w-14 shrink-0">{s.symbol}</span>
                {/* Ortadan iki yöne büyüyen çubuk: kâr sağa, zarar sola. */}
                <div className="flex-1 flex items-center h-2 min-w-0">
                  <div className="w-1/2 flex justify-end">
                    {!pozitif && (
                      <div
                        className="h-2 rounded-l-full bg-[#F43F5E]"
                        style={{ width: `${(Math.abs(s.pnl) / enBuyuk) * 100}%` }}
                      />
                    )}
                  </div>
                  <div className="w-px h-3 bg-[#242B35] shrink-0" />
                  <div className="w-1/2">
                    {pozitif && (
                      <div
                        className="h-2 rounded-r-full bg-[#10B981]"
                        style={{ width: `${(s.pnl / enBuyuk) * 100}%` }}
                      />
                    )}
                  </div>
                </div>
                <span
                  className="text-[11px] font-semibold tabular-nums w-24 text-right shrink-0"
                  style={{ color: pozitif ? "#10B981" : "#F43F5E" }}
                >
                  {tl(s.pnl)}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <p className="text-[9px] text-gray-600 leading-relaxed flex items-start gap-1.5 border-t border-[#242B35] pt-3">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        <span>
          Yalnızca <strong>kapanmış</strong> işlemler sayılır; açık pozisyonlardaki
          kâr/zarar buraya girmez. Tutma süresi, satılan adetlerin en eski alımdan
          eşleştirilmesiyle (FIFO) hesaplanır — alım kaydı bulunmayan satışlar
          ortalamaya katılmaz.
        </span>
      </p>
    </div>
  );
}
