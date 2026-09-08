"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Trophy, Crown, Medal, Award } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface HallOfFameEntry {
  period: string;
  period_label: string;
  period_end_date: string;
  category: string;
  rank: number;
  username: string;
  metric_value: number;
}

type Periyot = "weekly" | "monthly";
type Kategori = "GETIRI" | "ISTIKRAR" | "AKTIFLIK";

const KATEGORI_SEKMELERI: { key: Kategori; label: string }[] = [
  { key: "GETIRI", label: "Getiri" },
  { key: "ISTIKRAR", label: "İstikrar" },
  { key: "AKTIFLIK", label: "Aktiflik" },
];

const DEGER_BIRIMI: Record<Kategori, (v: number) => string> = {
  GETIRI: (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`,
  ISTIKRAR: (v) => v.toFixed(2),
  AKTIFLIK: (v) => `${Math.round(v)} işlem`,
};

const RANK_IKON: Record<number, React.ElementType> = { 1: Crown, 2: Medal, 3: Award };
const RANK_RENK: Record<number, string> = {
  1: "text-[#F59E0B] bg-[#F59E0B]/10 border-[#F59E0B]/30",
  2: "text-slate-300 bg-slate-400/10 border-slate-400/30",
  3: "text-orange-400 bg-orange-400/10 border-orange-400/30",
};

export default function HallOfFamePage() {
  const [periyot, setPeriyot] = useState<Periyot>("weekly");
  const [kategori, setKategori] = useState<Kategori>("GETIRI");
  const [kayitlar, setKayitlar] = useState<HallOfFameEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/hall-of-fame?period=${periyot}&category=${kategori}&limit=12`);
        if (res.ok && !cancelled) setKayitlar(await res.json());
      } catch (err) {
        console.error("Şampiyonlar Duvarı alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [periyot, kategori]);

  // period_label'a göre grupla: her dönem kendi kartında, rank sırasıyla.
  const donemler: Record<string, HallOfFameEntry[]> = {};
  for (const k of kayitlar) {
    (donemler[k.period_label] ??= []).push(k);
  }
  const donemEtiketleri = Object.keys(donemler).sort().reverse();

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Trophy className="w-5 h-5 text-[#F59E0B]" /> Şampiyonlar Duvarı
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Kapanmış her haftanın/ayın ilk 3'ü burada kalıcı olarak arşivlenir. Bir
          dönem henüz kapanmadıysa (bkz. anasayfadaki canlı liderlik tablosu)
          burada görünmez.
        </p>
      </div>

      <div className="flex items-center gap-1 bg-[#0B0E14] border border-[#242B35] rounded-lg p-1 max-w-xs">
        {([["weekly", "Haftalık"], ["monthly", "Aylık"]] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setPeriyot(key)}
            className={`flex-1 min-h-[36px] text-[11px] font-semibold rounded-md transition ${
              periyot === key ? "bg-[#242B35] text-white" : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1.5 overflow-x-auto">
        {KATEGORI_SEKMELERI.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setKategori(opt.key)}
            className={`shrink-0 px-3 min-h-[36px] text-xs font-bold rounded-lg transition ${
              kategori === opt.key ? "bg-[#10B981] text-[#0B0E14]" : "bg-[#151921] text-gray-400 border border-[#242B35] hover:text-gray-200"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-center py-10 text-gray-500 text-xs">Yükleniyor...</p>
      ) : donemEtiketleri.length === 0 ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center">
          <p className="text-xs text-gray-500">
            Henüz kapanmış bir {periyot === "weekly" ? "hafta" : "ay"} arşivlenmedi.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {donemEtiketleri.map((etiket) => (
            <div key={etiket} className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-3">{etiket}</h3>
              <div className="space-y-2">
                {donemler[etiket]
                  .sort((a, b) => a.rank - b.rank)
                  .map((k) => {
                    const Icon = RANK_IKON[k.rank] || Award;
                    return (
                      <div
                        key={k.rank}
                        className={`flex items-center justify-between p-2.5 rounded-lg border ${RANK_RENK[k.rank] || "text-gray-400 bg-[#0B0E14] border-[#242B35]"}`}
                      >
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4 shrink-0" strokeWidth={1.5} />
                          <Link href={`/profil/${k.username}`} className="text-xs font-bold hover:underline">
                            @{k.username}
                          </Link>
                        </div>
                        <span className="text-xs font-semibold tabular-nums">
                          {DEGER_BIRIMI[kategori](k.metric_value)}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
