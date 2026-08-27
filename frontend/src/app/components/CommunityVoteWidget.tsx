"use client";

import React, { useCallback, useEffect, useState } from "react";
import { TrendingUp, TrendingDown, BarChart3 } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface VoteData {
  symbol: string;
  up_count: number;
  down_count: number;
  total_votes: number;
  up_pct: number;
  down_pct: number;
  user_vote: string | null;
}

/**
 * Hisse bazlı topluluk beklenti anketi (road_map.md #6).
 *
 * Yorum tabanlı CommunitySentimentGauge'dan AYRIDIR: orası yazılmış yorumların
 * metin analizinden beslenir, burası tek tıkla verilen doğrudan oydur. Yorum
 * yazmak yüksek sürtünmeli olduğu için veri toplamak adına bu ayrım anlamlı —
 * yorum yokken de bu widget çalışır.
 */
export default function CommunityVoteWidget({ symbol }: { symbol: string }) {
  const { token } = useAuth();
  const [data, setData] = useState<VoteData | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/vote`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("Topluluk beklentisi alınamadı:", err);
    }
  }, [symbol, token]);

  useEffect(() => {
    load();
  }, [load]);

  const vote = async (direction: "UP" | "DOWN") => {
    if (!token || submitting) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/vote`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ direction }),
      });
      // Sunucu güncel sayımı zaten döndürüyor; ayrıca GET atmaya gerek yok.
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("Oy gönderilemedi:", err);
    } finally {
      setSubmitting(false);
    }
  };

  if (!token || !data) return null;

  const hasVotes = data.total_votes > 0;
  const myVote = data.user_vote;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <BarChart3 className="w-4 h-4 text-[#F59E0B]" />
        <h4 className="text-xs font-bold text-white uppercase tracking-wide">Topluluk Beklentisi</h4>
      </div>

      {hasVotes ? (
        <>
          <div className="w-full h-2.5 rounded-full overflow-hidden flex bg-[#0B0E14]">
            <div className="h-full bg-[#10B981]" style={{ width: `${data.up_pct}%` }} />
            <div className="h-full bg-[#F43F5E]" style={{ width: `${data.down_pct}%` }} />
          </div>
          <div className="flex justify-between text-[10px]">
            <span className="text-[#10B981] font-semibold">%{data.up_pct.toFixed(0)} Yükselir</span>
            <span className="text-[#F43F5E] font-semibold">%{data.down_pct.toFixed(0)} Düşer</span>
          </div>
        </>
      ) : (
        <p className="text-[11px] text-gray-500">
          Henüz oy verilmemiş. İlk oyu siz verin.
        </p>
      )}

      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => vote("UP")}
          disabled={submitting}
          type="button"
          className={`flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-bold transition disabled:opacity-50 ${
            myVote === "UP"
              ? "bg-[#4A87C7] text-[#0B0E14]"
              : "bg-[#0B0E14] border border-[#242B35] text-gray-300 hover:text-[#4A87C7] hover:border-[#4A87C7]/40"
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" /> Yükselir
        </button>
        <button
          onClick={() => vote("DOWN")}
          disabled={submitting}
          type="button"
          className={`flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-bold transition disabled:opacity-50 ${
            myVote === "DOWN"
              ? "bg-[#F43F5E] text-white"
              : "bg-[#0B0E14] border border-[#242B35] text-gray-300 hover:text-[#F43F5E] hover:border-[#F43F5E]/40"
          }`}
        >
          <TrendingDown className="w-3.5 h-3.5" /> Düşer
        </button>
      </div>

      <p className="text-[10px] text-gray-600">
        {data.total_votes} oy
        {myVote && " · Oyunuzu değiştirmek için diğerine tıklayın"}
        {" · "}Yatırım tavsiyesi değildir.
      </p>
    </div>
  );
}
