"use client";

import React, { useEffect, useState } from "react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Quote {
  symbol: string;
  label: string;
  price: number;
  change_1d_pct: number | null;
  change_30d_pct: number | null;
  as_of: string | null;
}

/** Sembole göre ondalık: kur/altın kuruş hassasiyetinde, endeks tam sayı okunur. */
function fmtPrice(symbol: string, v: number): string {
  const digits = symbol === "XU100" ? 0 : 2;
  return v.toLocaleString("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/**
 * Döviz kurları, gram altın ve BIST 100 şeridi.
 *
 * Türk yatırımcının hisse yanında sürekli izlediği referanslar; ücretli
 * platformlarda paket içinde sunulur, veri kaynağımızda ücretsiz olduğu için
 * burada da gösterilir. Değerler gün sonu kapanışlarıdır (anlık değildir).
 */
export default function MarketQuotesBar({ refreshKey }: { refreshKey?: number }) {
  const { refreshTrigger } = useAuth();
  const [quotes, setQuotes] = useState<Quote[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/market/quotes`);
        if (res.ok && !cancelled) setQuotes(await res.json());
      } catch (err) {
        console.error("Piyasa göstergeleri alınamadı:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [refreshKey, refreshTrigger]);

  if (quotes.length === 0) return null;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {quotes.map((q) => {
          const ch = q.change_1d_pct;
          const positive = (ch ?? 0) >= 0;
          const color = ch === null ? "#8A99AD" : positive ? "#10B981" : "#F43F5E";
          return (
            <div key={q.symbol} className="min-w-0">
              <p className="text-[10px] text-gray-500 truncate">{q.label}</p>
              <p className="text-base font-bold text-white tabular-nums">
                {fmtPrice(q.symbol, q.price)}
              </p>
              <div className="flex items-center gap-2 text-[10px] tabular-nums">
                <span style={{ color }}>
                  {ch === null ? "—" : `${positive ? "+" : ""}${ch.toFixed(2)}%`}
                </span>
                {q.change_30d_pct !== null && (
                  <span className="text-gray-600">
                    30g {q.change_30d_pct >= 0 ? "+" : ""}
                    {q.change_30d_pct.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-gray-600 mt-3 border-t border-[#242B35] pt-2.5">
        Gün sonu kapanış değerleridir, anlık değildir. Gram altın, ons altın ve
        dolar kurundan türetilmiştir.
      </p>
    </div>
  );
}
