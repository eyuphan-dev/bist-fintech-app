"use client";

import React, { useEffect, useState } from "react";
import { ShieldAlert, Info } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";
import { marketColor } from "../../lib/marketColor";

interface RiskData {
  day_count: number;
  annualized_return_pct: number | null;
  annualized_volatility_pct: number | null;
  max_drawdown_pct: number | null;
  max_drawdown_date: string | null;
  return_risk_ratio: number | null;
  beta_vs_index: number | null;
  best_day_pct: number | null;
  worst_day_pct: number | null;
  positive_day_ratio: number | null;
  risk_label: string | null;
  message: string | null;
}

const RISK_COLORS: Record<string, string> = {
  "Düşük": "#10B981",
  "Orta": "#F59E0B",
  "Yüksek": "#F43F5E",
};

/** Beta'yı sade Türkçeyle açıklar — çoğu kullanıcı için "1.3" tek başına anlamsız. */
function betaText(beta: number): string {
  if (beta > 1.15) return `Endeksten daha oynak — BIST %1 hareket ettiğinde portföyünüz ~%${beta.toFixed(1)} hareket ediyor.`;
  if (beta < 0.85) return `Endeksten daha sakin — BIST %1 hareket ettiğinde portföyünüz ~%${beta.toFixed(1)} hareket ediyor.`;
  return "Endeksle benzer oynaklıkta hareket ediyor.";
}

/**
 * Portföy risk profili — ücretli terminallerin "portföy optimizasyonu"
 * başlığı altında sunduğu ölçüler. Hepsi kendi gün sonu portföy
 * değerlerimizden hesaplanır.
 */
export default function PortfolioRiskPanel({ refreshKey }: { refreshKey?: number }) {
  const { token } = useAuth();
  const [data, setData] = useState<RiskData | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/portfolio/risk`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Risk metrikleri alınamadı:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [token, refreshKey]);

  // Veri yetersizse paneli hiç gösterme — boş kutu kafa karıştırır.
  if (!data || data.message) return null;

  const vol = data.annualized_volatility_pct;
  const color = RISK_COLORS[data.risk_label ?? ""] ?? "#8A99AD";

  const tiles = [
    {
      label: "Oynaklık (yıllık)",
      value: vol === null ? "—" : `%${vol.toFixed(1)}`,
      sub: data.risk_label ?? "",
      color,
    },
    {
      label: "En Büyük Düşüş",
      value: data.max_drawdown_pct === null ? "—" : `%${data.max_drawdown_pct.toFixed(1)}`,
      sub: "zirveden dibe",
      color: "#F43F5E",
    },
    {
      label: "Getiri / Risk",
      value: data.return_risk_ratio === null ? "—" : data.return_risk_ratio.toFixed(2),
      sub: "birim risk başına",
      color: marketColor(data.return_risk_ratio),
    },
    {
      label: "Artıda Kapanan Gün",
      value: data.positive_day_ratio === null ? "—" : `%${data.positive_day_ratio.toFixed(0)}`,
      sub: `${data.day_count} günde`,
      color: "#F8FAFC",
    },
  ];

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-2">
        <ShieldAlert className="w-4 h-4 text-[#F59E0B]" />
        <h3 className="text-xs font-bold text-white uppercase tracking-wide">Risk Profili</h3>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {tiles.map((t) => (
          <div key={t.label}>
            <p className="text-[10px] text-gray-500 mb-0.5">{t.label}</p>
            <p className="text-lg font-bold tabular-nums" style={{ color: t.color }}>{t.value}</p>
            <p className="text-[10px] text-gray-600">{t.sub}</p>
          </div>
        ))}
      </div>

      {data.beta_vs_index !== null && (
        <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg px-3 py-2.5">
          <div className="flex items-baseline gap-2">
            <span className="text-[10px] text-gray-500 uppercase font-bold">Beta</span>
            <span className="text-sm font-bold text-white tabular-nums">{data.beta_vs_index.toFixed(2)}</span>
          </div>
          <p className="text-[10px] text-gray-500 mt-0.5">{betaText(data.beta_vs_index)}</p>
        </div>
      )}

      {(data.best_day_pct !== null || data.worst_day_pct !== null) && (
        <div className="flex items-center gap-4 text-[10px] text-gray-500">
          <span>
            En iyi gün:{" "}
            <span className="text-[#10B981] font-semibold tabular-nums">
              +%{data.best_day_pct?.toFixed(2)}
            </span>
          </span>
          <span>
            En kötü gün:{" "}
            <span className="text-[#F43F5E] font-semibold tabular-nums">
              %{data.worst_day_pct?.toFixed(2)}
            </span>
          </span>
        </div>
      )}

      <p className="text-[10px] text-gray-600 flex items-start gap-1.5 border-t border-[#242B35] pt-3">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        <span>
          Oynaklık, günlük değer değişimlerinizin yıllıklandırılmış standart sapmasıdır —
          yüksek olması hem daha çok kazanma hem daha çok kaybetme ihtimali demektir.
          Geçmiş veriye dayanır, geleceği garanti etmez.
        </span>
      </p>
    </div>
  );
}
