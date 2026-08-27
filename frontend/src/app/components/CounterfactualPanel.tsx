"use client";

import React, { useEffect, useState } from "react";
import { GitCompareArrows, Info } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Scenario {
  key: string;
  label: string;
  final_value: number;
  return_pct: number;
}

interface CounterfactualData {
  available: boolean;
  reason: string | null;
  actual_value: number | null;
  actual_return_pct: number | null;
  baseline_capital: number | null;
  scenarios: Scenario[];
  note: string | null;
}

function fmtTL(v: number): string {
  return v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * "Sen olmasan ne olurdu?" karnesi.
 *
 * Rakiplerin sunmadığı bir kıyas: kullanıcının gerçek kararının maliyetini,
 * hiç işlem yapmama / sermayeyi toptan BIST 100'e yatırma / aylık eşit
 * parçalarla (DCA) yatırma senaryolarıyla karşılaştırır. Tüm değerler
 * backend'de counterfactual.py'de, kullanıcının kendi geçmişinden ve
 * XU100 kapanışlarından hesaplanır — uydurma bir varsayım yoktur.
 */
export default function CounterfactualPanel({ refreshKey }: { refreshKey?: number }) {
  const { token } = useAuth();
  const [data, setData] = useState<CounterfactualData | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/portfolio/counterfactual`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Karşı-olgu karnesi alınamadı:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [token, refreshKey]);

  // Yeterli veri yoksa özellik tümüyle gizlenir — uydurma bir sayı yerine.
  if (!data || !data.available || data.actual_value === null) return null;

  const gercekGetiri = data.actual_return_pct ?? 0;
  const enIyiSenaryo = data.scenarios.reduce(
    (best, s) => (s.return_pct > best.return_pct ? s : best),
    data.scenarios[0]
  );
  const gercekEnIyisindenKotu = enIyiSenaryo && gercekGetiri < enIyiSenaryo.return_pct;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5 space-y-4">
      <div className="flex items-center gap-2">
        <GitCompareArrows className="w-4 h-4 text-[#F59E0B]" />
        <h3 className="text-sm font-bold text-white tracking-wide uppercase">
          Sen Olmasan Ne Olurdu?
        </h3>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {/* Gerçek sonuç, diğer senaryolardan görsel olarak ayrışsın diye vurgulu. */}
        <div className="rounded-xl border border-[#F59E0B]/40 bg-[#F59E0B]/5 p-3">
          <p className="text-[9px] text-[#F59E0B] uppercase font-bold">Gerçek Sonucun</p>
          <p className="text-sm font-bold text-white tabular-nums mt-1">{fmtTL(data.actual_value)} TL</p>
          <p
            className="text-[10px] font-semibold tabular-nums mt-0.5"
            style={{ color: gercekGetiri >= 0 ? "#10B981" : "#F43F5E" }}
          >
            {gercekGetiri >= 0 ? "+" : ""}{gercekGetiri.toFixed(2)}%
          </p>
        </div>

        {data.scenarios.map((s) => (
          <div key={s.key} className="rounded-xl border border-[#242B35] p-3">
            <p className="text-[9px] text-gray-500 uppercase font-bold leading-tight">{s.label}</p>
            <p className="text-sm font-bold text-white tabular-nums mt-1">{fmtTL(s.final_value)} TL</p>
            <p
              className="text-[10px] font-semibold tabular-nums mt-0.5"
              style={{ color: s.return_pct >= 0 ? "#10B981" : "#F43F5E" }}
            >
              {s.return_pct >= 0 ? "+" : ""}{s.return_pct.toFixed(2)}%
            </p>
          </div>
        ))}
      </div>

      {gercekEnIyisindenKotu && (
        <p className="text-[11px] text-gray-400 bg-[#0B0E14] rounded-lg px-3 py-2">
          Bu dönemde <span className="text-[#F59E0B] font-semibold">{enIyiSenaryo.label.toLowerCase()}</span> senaryosu
          gerçek sonucundan daha iyi olurdu. Bu, işlemlerinin yanlış olduğu anlamına gelmez —
          BIST 100 bu dönemde güçlü performans gösterdi; kıyaslama fikir vermek içindir.
        </p>
      )}

      {data.note && (
        <p className="text-[9px] text-gray-600 flex items-start gap-1.5">
          <Info className="w-3 h-3 shrink-0 mt-0.5" />
          {data.note}
        </p>
      )}
    </div>
  );
}
