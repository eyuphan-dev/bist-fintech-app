"use client";

import React, { useEffect, useState } from "react";
import { Users } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

interface SentimentData {
  symbol: string;
  total_comments: number;
  positive_pct: number;
  negative_pct: number;
  neutral_pct: number;
  verdict_text: string;
}

interface CommunitySentimentGaugeProps {
  symbol: string;
  refreshTrigger?: number;
}

/** Topluluk yorumlarını toplulaştırıp "Topluluk Hissede Boğa (%78 Olumlu)" benzeri özet gösterir. */
export default function CommunitySentimentGauge({ symbol, refreshTrigger }: CommunitySentimentGaugeProps) {
  const [data, setData] = useState<SentimentData | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchSentiment = async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/sentiment`);
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Topluluk duyarlılığı alınamadı:", err);
      }
    };
    fetchSentiment();
    return () => {
      cancelled = true;
    };
  }, [symbol, refreshTrigger]);

  if (!data || data.total_comments === 0) return null;

  const isBullish = data.positive_pct >= 55;
  const isBearish = data.negative_pct >= 55;
  const verdictColor = isBullish ? "text-[#10B981]" : isBearish ? "text-[#F43F5E]" : "text-[#F59E0B]";

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Users className="w-4 h-4 text-[#F59E0B]" />
        <h4 className="text-xs font-bold text-white uppercase tracking-wide">Topluluk Duyarlılığı</h4>
      </div>

      <p className={`text-sm font-bold ${verdictColor}`}>{data.verdict_text}</p>

      <div className="w-full h-2.5 rounded-full overflow-hidden flex bg-[#0B0E14]">
        <div className="h-full bg-[#10B981]" style={{ width: `${data.positive_pct}%` }} />
        <div className="h-full bg-[#242B35]" style={{ width: `${data.neutral_pct}%` }} />
        <div className="h-full bg-[#F43F5E]" style={{ width: `${data.negative_pct}%` }} />
      </div>

      <div className="flex justify-between text-[10px] text-gray-500">
        <span className="text-[#10B981]">%{data.positive_pct.toFixed(0)} Olumlu</span>
        <span>%{data.neutral_pct.toFixed(0)} Nötr</span>
        <span className="text-[#F43F5E]">%{data.negative_pct.toFixed(0)} Olumsuz</span>
      </div>

      <p className="text-[10px] text-gray-600">{data.total_comments} yoruma dayanmaktadır.</p>
    </div>
  );
}
