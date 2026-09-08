"use client";

import React, { useEffect, useState } from "react";
import { ListChecks, RefreshCw, CheckCircle2, Circle, Star } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Quest {
  id: string;
  isim: string;
  aciklama: string;
  puan: number;
  tamamlandi: boolean;
}

export default function QuestsPage() {
  const { token, loading: authLoading, refreshTrigger } = useAuth();
  const [quests, setQuests] = useState<Quest[]>([]);
  const [gamePoints, setGamePoints] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const [qRes, pRes] = await Promise.all([
          fetch(`${API_BASE}/quests`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API_BASE}/user/game-points`, { headers: { Authorization: `Bearer ${token}` } }),
        ]);
        if (qRes.ok && !cancelled) setQuests(await qRes.json());
        if (pRes.ok && !cancelled) setGamePoints((await pRes.json()).game_points);
      } catch (err) {
        console.error("Görevler alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token, refreshTrigger]);

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
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 text-center">
          <p className="text-xs text-gray-400">Görevlerini görmek için giriş yapmalısın.</p>
        </div>
      </div>
    );
  }

  const tamamlananSayisi = quests.filter((q) => q.tamamlandi).length;

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <ListChecks className="w-5 h-5 text-[#10B981]" /> Haftalık Görevler
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Her Pazartesi sıfırlanır. Tamamladığın her görev, sanal ödül
          mağazasında harcayabileceğin oyun puanı kazandırır — gerçek parayla
          hiçbir ilişkisi yoktur.
        </p>
      </div>

      {!loading && (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex items-center gap-3">
          <Star className="w-8 h-8 text-[#F59E0B] shrink-0" strokeWidth={1.5} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-white">{tamamlananSayisi} / {quests.length} görev tamamlandı</p>
            <div className="w-full max-w-[160px] h-1.5 bg-[#0B0E14] rounded-full overflow-hidden mt-1.5">
              <div
                className="h-full bg-[#10B981] rounded-full transition-all"
                style={{ width: `${quests.length ? (tamamlananSayisi / quests.length) * 100 : 0}%` }}
              />
            </div>
          </div>
          <div className="text-right shrink-0">
            <p className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">Oyun Puanı</p>
            <p className="text-lg font-bold text-[#F59E0B] tabular-nums">{gamePoints ?? "—"}</p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center">
          <p className="text-xs text-gray-500">Yükleniyor...</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {quests.map((q) => (
            <div
              key={q.id}
              className={`rounded-xl p-4 border flex items-start gap-3 ${
                q.tamamlandi ? "bg-[#10B981]/10 border-[#10B981]/30" : "bg-[#151921] border-[#242B35]"
              }`}
            >
              {q.tamamlandi ? (
                <CheckCircle2 className="w-5 h-5 text-[#10B981] shrink-0 mt-0.5" />
              ) : (
                <Circle className="w-5 h-5 text-gray-600 shrink-0 mt-0.5" />
              )}
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-bold ${q.tamamlandi ? "text-white" : "text-gray-300"}`}>{q.isim}</p>
                <p className="text-xs text-gray-500 mt-0.5">{q.aciklama}</p>
              </div>
              <span className="text-xs font-bold text-[#F59E0B] shrink-0 tabular-nums">+{q.puan}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
