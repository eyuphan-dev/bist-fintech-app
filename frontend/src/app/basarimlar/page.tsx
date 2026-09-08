"use client";

import React, { useEffect, useState } from "react";
import {
  Trophy, RefreshCw, Lock, Footprints, Activity, Layers, TrendingUp,
  ShieldCheck, Coins, CalendarCheck, Award, PiggyBank, Target, Eye,
  MessageCircle, Compass, ListChecks, UserPlus, Moon, Swords, Crown, Star,
} from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Achievement {
  id: string;
  isim: string;
  aciklama: string;
  kazanildi: boolean;
  kazanilma_tarihi: string | null;
}

const IKON_HARITASI: Record<string, React.ElementType> = {
  "ilk-adim": Footprints,
  "aktif-yatirimci": Activity,
  "deneyimli-trader": Trophy,
  "cesitlendirme-ustasi": Layers,
  "kar-makinesi": TrendingUp,
  "katilim-sadigi": ShieldCheck,
  "temettu-avcisi": Coins,
  "sadik-uye": CalendarCheck,
  "ilk-kar": PiggyBank,
  "keskin-nisanci": Target,
  "takipci": Eye,
  "sosyal-yatirimci": MessageCircle,
  "kahin-adayi": Compass,
  "stratejist": ListChecks,
  "topluluk-elcisi": UserPlus,
  "gece-kusu": Moon,
  "duello-galibi": Swords,
  "sampiyon": Crown,
  "puan-avcisi": Star,
};

export default function AchievementsPage() {
  const { token, loading: authLoading, refreshTrigger } = useAuth();
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/achievements`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && !cancelled) setAchievements(await res.json());
      } catch (err) {
        console.error("Başarım verisi alınamadı:", err);
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
      <div className="max-w-4xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 text-center">
          <p className="text-xs text-gray-400">Başarımlarını görmek için giriş yapmalısın.</p>
        </div>
      </div>
    );
  }

  const kazanilanSayisi = achievements.filter((a) => a.kazanildi).length;

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Trophy className="w-5 h-5 text-[#F59E0B]" /> Başarımlar
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Platformdaki aktifliğine göre kazandığın rozetler. Bir rozeti kazandıktan
          sonra koşulu daha sonra geçerliliğini yitirse bile rozet elinde kalır.
        </p>
      </div>

      {!loading && (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex items-center gap-3">
          <Award className="w-8 h-8 text-[#F59E0B] shrink-0" strokeWidth={1.5} />
          <div>
            <p className="text-sm font-bold text-white">{kazanilanSayisi} / {achievements.length} rozet kazanıldı</p>
            <div className="w-40 h-1.5 bg-[#0B0E14] rounded-full overflow-hidden mt-1.5">
              <div
                className="h-full bg-[#F59E0B] rounded-full transition-all"
                style={{ width: `${achievements.length ? (kazanilanSayisi / achievements.length) * 100 : 0}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center">
          <p className="text-xs text-gray-500">Yükleniyor...</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {achievements.map((a) => {
            const Icon = IKON_HARITASI[a.id] ?? Award;
            return (
              <div
                key={a.id}
                className={`rounded-xl p-4 border flex flex-col items-center text-center gap-2 ${
                  a.kazanildi
                    ? "bg-[#F59E0B]/10 border-[#F59E0B]/30"
                    : "bg-[#151921] border-[#242B35] opacity-60"
                }`}
              >
                <span
                  className={`w-11 h-11 rounded-full flex items-center justify-center relative ${
                    a.kazanildi ? "bg-[#F59E0B]/20 text-[#F59E0B]" : "bg-[#0B0E14] text-gray-600"
                  }`}
                >
                  <Icon className="w-5 h-5" strokeWidth={1.5} />
                  {!a.kazanildi && (
                    <span className="absolute -bottom-1 -right-1 w-5 h-5 rounded-full bg-[#242B35] flex items-center justify-center">
                      <Lock className="w-2.5 h-2.5 text-gray-500" />
                    </span>
                  )}
                </span>
                <p className={`text-xs font-bold ${a.kazanildi ? "text-white" : "text-gray-400"}`}>{a.isim}</p>
                <p className="text-[10px] text-gray-500 leading-snug">{a.aciklama}</p>
                {a.kazanildi && a.kazanilma_tarihi && (
                  <p className="text-[9px] text-[#F59E0B] font-semibold">
                    {new Date(a.kazanilma_tarihi).toLocaleDateString("tr-TR")}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
