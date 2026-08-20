"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Radar, ArrowRight, RefreshCw, Info } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Signal {
  symbol: string;
  company_name: string;
  signal_type: string;
  direction: string;
  title: string;
  detail: string;
  price: number;
}

type Filter = "ALL" | "AL" | "SAT" | "DIKKAT";

const DIRECTION_STYLE: Record<string, { color: string; bg: string; label: string }> = {
  AL: { color: "#10B981", bg: "rgba(16,185,129,0.1)", label: "Alış Yönlü" },
  SAT: { color: "#F43F5E", bg: "rgba(244,63,94,0.1)", label: "Satış Yönlü" },
  DIKKAT: { color: "#F59E0B", bg: "rgba(245,158,11,0.1)", label: "Dikkat" },
};

export default function SignalsPage() {
  const { token, loading: authLoading, refreshTrigger } = useAuth();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("ALL");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/signals`);
        if (res.ok && !cancelled) setSignals(await res.json());
      } catch (err) {
        console.error("Sinyaller alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [refreshTrigger]);

  if (authLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <RefreshCw className="w-10 h-10 text-[#10B981] animate-spin mb-4" />
        <p className="text-gray-400 font-medium">Yükleniyor...</p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5 text-center">
          <p className="text-xs text-gray-400">Sinyalleri görmek için giriş yapmalısınız.</p>
        </div>
      </div>
    );
  }

  const visible = signals.filter((s) => filter === "ALL" || s.direction === filter);
  const counts = {
    AL: signals.filter((s) => s.direction === "AL").length,
    SAT: signals.filter((s) => s.direction === "SAT").length,
    DIKKAT: signals.filter((s) => s.direction === "DIKKAT").length,
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Radar className="w-5 h-5 text-[#F59E0B]" /> Teknik Sinyal Taraması
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Tüm hisseler taranarak bugün oluşan teknik sinyaller listelenir: altın/ölüm
          kesişimi, RSI aşırı bölgeleri, hacim patlaması ve 52 hafta kırılımları.
        </p>
      </div>

      {loading ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-8 text-center">
          <p className="text-xs text-gray-500">Hisseler taranıyor...</p>
        </div>
      ) : signals.length === 0 ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-8 text-center">
          <Radar className="w-8 h-8 text-gray-600 mx-auto mb-2" />
          <p className="text-xs text-gray-400">Bugün için oluşmuş bir teknik sinyal yok.</p>
          <p className="text-[10px] text-gray-600 mt-1.5">
            Sinyaller yalnızca koşul o gün oluştuğunda listelenir; sakin günlerde liste boş olabilir.
          </p>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2 flex-wrap">
            {([
              ["ALL", `Tümü (${signals.length})`],
              ["AL", `Alış (${counts.AL})`],
              ["DIKKAT", `Dikkat (${counts.DIKKAT})`],
              ["SAT", `Satış (${counts.SAT})`],
            ] as [Filter, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                type="button"
                className={`px-3.5 py-3 md:py-1.5 rounded-lg text-[11px] font-semibold transition ${
                  filter === key
                    ? "bg-[#10B981] text-[#0B0E14]"
                    : "bg-[#151921] border border-[#242B35] text-gray-400 hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {visible.map((s, i) => {
              const style = DIRECTION_STYLE[s.direction] ?? DIRECTION_STYLE.DIKKAT;
              return (
                <Link
                  key={`${s.symbol}-${s.signal_type}-${i}`}
                  href={`/hisse/${s.symbol}`}
                  className="bg-[#151921] border border-[#242B35] hover:border-[#10B981]/40 rounded-2xl p-4 transition block"
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="min-w-0">
                      <p className="font-bold text-white flex items-center gap-1.5">
                        {s.symbol}
                        <ArrowRight className="w-3 h-3 text-gray-600" />
                      </p>
                      <p className="text-[10px] text-gray-500 truncate max-w-[180px]">
                        {s.company_name}
                      </p>
                    </div>
                    <span
                      className="text-[10px] font-bold px-2 py-1 rounded shrink-0"
                      style={{ color: style.color, backgroundColor: style.bg }}
                    >
                      {style.label}
                    </span>
                  </div>

                  <p className="text-xs font-bold mb-1" style={{ color: style.color }}>
                    {s.title}
                  </p>
                  <p className="text-[11px] text-gray-400 leading-relaxed">{s.detail}</p>
                  <p className="text-[10px] text-gray-600 mt-2 tabular-nums">
                    Fiyat: {s.price.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL
                  </p>
                </Link>
              );
            })}
          </div>

          {visible.length === 0 && (
            <p className="text-xs text-gray-500 text-center py-6">Bu filtreye uyan sinyal yok.</p>
          )}
        </>
      )}

      <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
        <p className="text-[10px] text-gray-500 flex items-start gap-1.5">
          <Info className="w-3 h-3 shrink-0 mt-0.5" />
          <span>
            Teknik sinyaller geçmiş fiyat hareketlerinden hesaplanan istatistiksel
            gözlemlerdir; geleceği tahmin etmez ve <strong>yatırım tavsiyesi değildir</strong>.
            Kesişim sinyalleri yalnızca koşul o gün oluştuğunda listelenir — aylar önce
            gerçekleşmiş bir kesişim her gün tekrar gösterilmez.
          </span>
        </p>
      </div>
    </div>
  );
}
