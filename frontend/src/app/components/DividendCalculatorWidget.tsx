"use client";

import React, { useState } from "react";
import { PiggyBank, Loader2 } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

interface DividendGoalResult {
  symbol: string;
  available: boolean;
  message?: string;
  current_price?: number;
  dividend_yield_pct?: number;
  target_monthly_income?: number;
  required_shares?: number;
  required_lots?: number;
  required_capital?: number;
}

interface DividendCalculatorWidgetProps {
  symbol: string;
}

/** Hedeflenen aylık temettü (pasif gelir) için gereken lot sayısı ve sermayeyi hesaplar. */
export default function DividendCalculatorWidget({ symbol }: DividendCalculatorWidgetProps) {
  const [targetIncome, setTargetIncome] = useState<number>(5000);
  const [result, setResult] = useState<DividendGoalResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleCalculate = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/dividend-goal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_monthly_income: targetIncome }),
      });
      if (res.ok) setResult(await res.json());
    } catch (err) {
      console.error("Temettü hedefi hesaplama hatası:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-3">
      <div className="flex items-center gap-2">
        <PiggyBank className="w-4 h-4 text-[#F59E0B]" />
        <h4 className="text-xs font-bold text-white uppercase tracking-wide">Pasif Gelir Hedefi Hesaplayıcı</h4>
      </div>

      <div className="flex items-center gap-2">
        <div className="flex-1">
          <label className="text-[10px] text-gray-500 uppercase font-semibold">Aylık Hedef Gelir (TL)</label>
          <input
            type="number"
            min={1}
            className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#F59E0B] rounded-lg px-3 py-2 text-white text-sm tabular-nums outline-none transition"
            value={targetIncome}
            onChange={(e) => setTargetIncome(Math.max(1, Number(e.target.value) || 0))}
          />
        </div>
        <button
          onClick={handleCalculate}
          disabled={loading}
          className="mt-5 bg-[#F59E0B] hover:bg-[#d98a08] text-[#0B0E14] font-bold text-xs px-4 py-2 rounded-lg transition disabled:opacity-50 flex items-center gap-1.5"
        >
          {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Hesapla
        </button>
      </div>

      {result && (
        <div className="pt-2 border-t border-[#242B35]">
          {!result.available ? (
            <p className="text-[11px] text-gray-500">{result.message}</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-gray-500 text-[10px] uppercase">Gerekli Lot Sayısı</span>
                <p className="text-lg font-bold text-white tabular-nums">
                  {result.required_lots?.toLocaleString("tr-TR")}
                </p>
              </div>
              <div>
                <span className="text-gray-500 text-[10px] uppercase">Gerekli Sermaye</span>
                <p className="text-lg font-bold text-[#F59E0B] tabular-nums">
                  {result.required_capital?.toLocaleString("tr-TR")} TL
                </p>
              </div>
              <div className="col-span-2 text-[10px] text-gray-500">
                Güncel temettü verimi: %{result.dividend_yield_pct?.toFixed(2)} · Fiyat: {result.current_price?.toFixed(2)} TL
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
