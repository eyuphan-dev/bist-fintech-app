"use client";

import React, { useEffect, useState } from "react";
import { Gift, Copy, Check, Users } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface ReferralInfo {
  code: string;
  referral_count: number;
  total_bonus: number;
}

export default function ReferralWidget() {
  const { token } = useAuth();
  const [info, setInfo] = useState<ReferralInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [kopyalandi, setKopyalandi] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/user/referral`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && !cancelled) setInfo(await res.json());
      } catch (err) {
        console.error("Referans bilgisi alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  const kopyala = () => {
    if (!info) return;
    navigator.clipboard?.writeText(info.code).then(() => {
      setKopyalandi(true);
      setTimeout(() => setKopyalandi(false), 2000);
    });
  };

  if (loading || !info) return null;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
      <div className="flex items-center gap-2 mb-1">
        <Gift className="w-4 h-4 text-[#F59E0B]" />
        <h3 className="text-sm font-bold text-white">Arkadaşını Davet Et</h3>
      </div>
      <p className="text-xs text-gray-500 mb-4">
        Kodunu paylaş, arkadaşın kayıt olurken girsin — ikiniz de 5.000 TL sanal bonus kazanır.
      </p>

      <div className="flex items-center gap-2 mb-4">
        <span className="flex-1 min-w-0 min-h-[44px] flex items-center justify-center px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white font-bold text-lg tracking-widest tabular-nums">
          {info.code}
        </span>
        <button
          onClick={kopyala}
          className="shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg bg-[#242B35] hover:bg-[#2E3641] text-white transition"
          title="Kodu kopyala"
        >
          {kopyalandi ? <Check className="w-4 h-4 text-[#10B981]" /> : <Copy className="w-4 h-4" />}
        </button>
      </div>

      <div className="flex items-center gap-2 text-xs text-gray-400">
        <Users className="w-3.5 h-3.5" />
        <span>
          <span className="text-white font-semibold">{info.referral_count}</span> kişi davet ettin
          {info.total_bonus > 0 && (
            <> · toplam <span className="text-[#10B981] font-semibold">+{info.total_bonus.toLocaleString("tr-TR")} TL</span> bonus kazandın</>
          )}
        </span>
      </div>
    </div>
  );
}
