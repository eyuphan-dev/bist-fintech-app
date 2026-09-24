"use client";

import React, { useEffect, useMemo, useState } from "react";
import { RefreshCw, Globe2, ChevronDown, Info } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface MakroEtkinlik {
  tarih: string; // YYYY-MM-DD
  baslik: string;
  kategori: "TURKIYE" | "ABD" | "TATIL";
  onem: number;
  tahmini: boolean;
  aciklama: string;
}

type Filtre = "hepsi" | "TURKIYE" | "ABD" | "TATIL";

const FILTRELER: { id: Filtre; label: string }[] = [
  { id: "hepsi", label: "Tümü" },
  { id: "TURKIYE", label: "Türkiye" },
  { id: "ABD", label: "ABD" },
  { id: "TATIL", label: "Borsa Tatili" },
];

const KATEGORI_RENK: Record<string, string> = {
  TURKIYE: "#F43F5E",
  ABD: "#60A5FA",
  TATIL: "#F59E0B",
};

function gunFarki(tarih: string): number {
  const hedef = new Date(tarih + "T00:00:00");
  const bugun = new Date();
  bugun.setHours(0, 0, 0, 0);
  return Math.round((hedef.getTime() - bugun.getTime()) / 86400000);
}

function OnemNoktalari({ onem }: { onem: number }) {
  return (
    <span className="flex gap-0.5" title={`Önem: ${onem}/3`} aria-label={`Önem ${onem} / 3`}>
      {[1, 2, 3].map((n) => (
        <span key={n} className={`w-1.5 h-1.5 rounded-full ${n <= onem ? "bg-[#F59E0B]" : "bg-[#242B35]"}`} />
      ))}
    </span>
  );
}

export default function MakroTakvim() {
  const [etkinlikler, setEtkinlikler] = useState<MakroEtkinlik[] | null>(null);
  const [filtre, setFiltre] = useState<Filtre>("hepsi");
  const [acik, setAcik] = useState<string | null>(null);

  useEffect(() => {
    let iptal = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/macro-calendar?days=60`);
        if (!iptal) setEtkinlikler(res.ok ? await res.json() : []);
      } catch (err) {
        console.error("Makro takvim alınamadı:", err);
        if (!iptal) setEtkinlikler([]);
      }
    })();
    return () => { iptal = true; };
  }, []);

  const gorunen = useMemo(
    () => (etkinlikler ?? []).filter((e) => filtre === "hepsi" || e.kategori === filtre),
    [etkinlikler, filtre],
  );

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
          <Globe2 className="w-4 h-4 text-[#60A5FA]" /> Ekonomik Takvim (Önümüzdeki 60 Gün)
        </h2>
        <p className="text-[11px] text-gray-500 mt-1">
          Borsayı etkileyebilecek makro veri açıklamaları ve borsa tatilleri. Bir satıra dokunarak
          verinin piyasa için ne anlama geldiğini okuyabilirsin.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTRELER.map((f) => (
          <button
            key={f.id}
            onClick={() => setFiltre(f.id)}
            className={`min-h-[36px] px-3 rounded-lg text-[11px] font-bold border transition ${
              filtre === f.id ? "bg-[#242B35] border-[#3A4452] text-white" : "border-[#242B35] text-gray-400 hover:text-white"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {etkinlikler === null ? (
        <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
          Yükleniyor...
        </div>
      ) : gorunen.length === 0 ? (
        <p className="text-xs text-gray-500 py-6 text-center bg-[#151921] border border-[#242B35] rounded-xl">
          Bu aralıkta gösterilecek etkinlik yok.
        </p>
      ) : (
        <div className="space-y-2">
          {gorunen.map((e) => {
            const anahtar = `${e.tarih}-${e.baslik}`;
            const d = gunFarki(e.tarih);
            const renk = KATEGORI_RENK[e.kategori] ?? "#8A99AD";
            const genis = acik === anahtar;
            return (
              <button
                key={anahtar}
                onClick={() => setAcik(genis ? null : anahtar)}
                className="w-full text-left bg-[#151921] border border-[#242B35] hover:border-[#3A4452] rounded-xl p-3.5 transition"
                aria-expanded={genis}
              >
                <div className="flex items-center gap-3">
                  <div className="w-12 shrink-0 text-center">
                    <p className="text-sm font-bold text-white tabular-nums leading-none">
                      {new Date(e.tarih + "T00:00:00").getDate()}
                    </p>
                    <p className="text-[10px] text-gray-500 uppercase">
                      {new Date(e.tarih + "T00:00:00").toLocaleDateString("tr-TR", { month: "short" })}
                    </p>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-white break-words">{e.baslik}</p>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <span className="text-[10px] font-bold" style={{ color: renk }}>
                        {e.kategori === "TURKIYE" ? "Türkiye" : e.kategori === "ABD" ? "ABD" : "Tatil"}
                      </span>
                      {e.tahmini && (
                        <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#242B35] text-gray-400">
                          tahmini tarih
                        </span>
                      )}
                      <OnemNoktalari onem={e.onem} />
                      <span className="text-[10px] text-gray-500">
                        {d === 0 ? "Bugün" : d === 1 ? "Yarın" : `${d} gün sonra`}
                      </span>
                    </div>
                  </div>
                  <ChevronDown className={`w-4 h-4 text-gray-500 shrink-0 transition-transform ${genis ? "rotate-180" : ""}`} />
                </div>
                {genis && <p className="text-[11px] text-gray-400 mt-3 pl-15 leading-relaxed">{e.aciklama}</p>}
              </button>
            );
          })}
        </div>
      )}

      <p className="text-[10px] text-gray-600 flex items-start gap-1.5">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        <span>
          Tarihler kural tabanlıdır; "tahmini" işaretliler yaklaşık günü gösterir, kesin tarih için
          resmi kurumun (TÜİK, TCMB, ABD BLS) takvimine bak. Açıklamalar genel bilgidir, yatırım
          tavsiyesi değildir.
        </span>
      </p>
    </section>
  );
}
