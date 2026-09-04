"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  User as UserIcon, RefreshCw, Lock, Calendar, Trophy, PieChart,
  Footprints, Activity, Layers, TrendingUp, ShieldCheck, Coins, CalendarCheck, Award,
} from "lucide-react";
import { useAuth, API_BASE } from "../../context/AuthContext";
import { marketTextClass } from "../../../lib/marketColor";

interface PublicProfileHolding {
  symbol: string;
  company_name: string;
  weight_pct: number;
}

interface Achievement {
  id: string;
  isim: string;
  aciklama: string;
  kazanildi: boolean;
  kazanilma_tarihi: string | null;
}

interface PublicProfile {
  username: string;
  created_at: string;
  total_portfolio_value: number;
  profit_loss_pct: number;
  achievements: Achievement[];
  top_holdings: PublicProfileHolding[];
  profile_public: boolean;
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
};

export default function PublicProfilePage() {
  const params = useParams<{ username: string }>();
  const { token, user, loading: authLoading } = useAuth();
  const [profile, setProfile] = useState<PublicProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !params.username) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/users/${encodeURIComponent(params.username)}/profile`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (cancelled) return;
        if (res.ok) {
          setProfile(data);
        } else {
          setError(data.detail || "Profil yüklenemedi.");
        }
      } catch {
        if (!cancelled) setError("Sunucuya bağlanılamadı.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token, params.username]);

  if (authLoading || loading) {
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
          <p className="text-xs text-gray-400">Profilleri görmek için giriş yapmalısın.</p>
        </div>
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center space-y-2">
          <Lock className="w-8 h-8 text-gray-600 mx-auto" strokeWidth={1.5} />
          <p className="text-sm font-bold text-white">Profil görüntülenemiyor</p>
          <p className="text-xs text-gray-500">{error || "Kullanıcı bulunamadı."}</p>
        </div>
      </div>
    );
  }

  const kazanilanlar = profile.achievements.filter((a) => a.kazanildi);
  const isSelf = user?.username === profile.username;

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 flex items-center gap-4">
        <span className="w-14 h-14 rounded-full bg-[#C46D2C]/15 border border-[#C46D2C]/30 flex items-center justify-center shrink-0">
          <UserIcon className="w-7 h-7 text-[#C46D2C]" strokeWidth={1.5} />
        </span>
        <div className="min-w-0">
          <h1 className="text-lg font-bold text-white truncate">@{profile.username}{isSelf && " (Sen)"}</h1>
          <p className="text-[11px] text-gray-500 flex items-center gap-1 mt-0.5">
            <Calendar className="w-3 h-3" />
            {new Date(profile.created_at).toLocaleDateString("tr-TR")} tarihinden beri üye
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
          <p className="text-[10px] text-gray-500 uppercase font-bold tracking-wide mb-1">Portföy Değeri</p>
          <p className="text-lg font-bold text-white tabular-nums">
            {profile.total_portfolio_value.toLocaleString("tr-TR")} TL
          </p>
        </div>
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
          <p className="text-[10px] text-gray-500 uppercase font-bold tracking-wide mb-1">Getiri</p>
          <p className={`text-lg font-bold tabular-nums ${marketTextClass(profile.profit_loss_pct)}`}>
            {profile.profit_loss_pct > 0 ? "+" : ""}{profile.profit_loss_pct.toFixed(2)}%
          </p>
        </div>
      </div>

      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
        <h3 className="text-sm font-bold text-white uppercase tracking-wide mb-3 flex items-center gap-1.5">
          <PieChart className="w-4 h-4 text-[#10B981]" /> En Büyük Pozisyonlar
        </h3>
        {profile.top_holdings.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-4">Henüz açık pozisyon yok.</p>
        ) : (
          <div className="space-y-2.5">
            {profile.top_holdings.map((h) => (
              <div key={h.symbol} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-white">{h.symbol}</span>
                  <span className="text-gray-400 tabular-nums">%{h.weight_pct.toFixed(1)}</span>
                </div>
                <div className="w-full h-1.5 bg-[#0B0E14] rounded-full overflow-hidden">
                  <div className="h-full bg-[#10B981] rounded-full" style={{ width: `${Math.min(100, h.weight_pct)}%` }} />
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="text-[10px] text-gray-600 mt-3">
          Yalnızca portföy içi ağırlık yüzdesi gösterilir; adet ve TL tutarı gizlidir.
        </p>
      </div>

      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
        <h3 className="text-sm font-bold text-white uppercase tracking-wide mb-3 flex items-center gap-1.5">
          <Trophy className="w-4 h-4 text-[#F59E0B]" /> Rozetler ({kazanilanlar.length})
        </h3>
        {kazanilanlar.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-4">Henüz kazanılmış bir rozet yok.</p>
        ) : (
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
            {kazanilanlar.map((a) => {
              const Icon = IKON_HARITASI[a.id] ?? Award;
              return (
                <div key={a.id} className="rounded-xl p-3 border bg-[#F59E0B]/10 border-[#F59E0B]/30 flex flex-col items-center text-center gap-1.5">
                  <span className="w-9 h-9 rounded-full flex items-center justify-center bg-[#F59E0B]/20 text-[#F59E0B]">
                    <Icon className="w-4 h-4" strokeWidth={1.5} />
                  </span>
                  <p className="text-[10px] font-bold text-white leading-snug">{a.isim}</p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
