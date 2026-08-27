"use client";

import React, { useState } from "react";
import { Calculator, Loader2, TrendingUp, TrendingDown, HelpCircle } from "lucide-react";
import CalculatorHelpModal from "./CalculatorHelpModal";
import { marketTextClass } from "../../lib/marketColor";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

interface DcaTimelinePoint {
  date: string;
  price: number;
  invested_cumulative: number;
  portfolio_value: number;
}

interface DcaBacktestResult {
  symbol: string;
  available: boolean;
  message?: string;
  months?: number;
  monthly_amount?: number;
  total_invested?: number;
  total_shares?: number;
  final_value?: number;
  profit?: number;
  profit_pct?: number;
  timeline?: DcaTimelinePoint[];
}

interface DcaBacktestWidgetProps {
  symbol: string;
}

/** Düzenli (her ay sabit tutar) yatırım stratejisinin geçmiş performansını geriye dönük test eder. */
export default function DcaBacktestWidget({ symbol }: DcaBacktestWidgetProps) {
  const [monthlyAmount, setMonthlyAmount] = useState<number>(1000);
  const [months, setMonths] = useState<number>(12);
  const [result, setResult] = useState<DcaBacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [showHelp, setShowHelp] = useState(false);

  const handleRun = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/dca-backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monthly_amount: monthlyAmount, months }),
      });
      if (res.ok) setResult(await res.json());
    } catch (err) {
      console.error("DCA backtest hatası:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-3">
      {showHelp && (
        <CalculatorHelpModal
          title="Ortalama Maliyet (DCA) Hesaplayıcı"
          purpose="Düzenli aralıklarla (her ay) sabit bir tutar yatırdığınızda, geçmiş fiyat verisine göre elde etmiş olacağınız ortalama birim maliyeti ve toplam getiriyi geriye dönük olarak simüle eder."
          howTo="Her ay yatıracağınız sabit tutarı (TL) ve simülasyon süresini (ay) girin, 'Simülasyonu Çalıştır'a basın. Sistem seçtiğiniz hissenin geçmiş fiyatlarını kullanarak toplam yatırım, güncel değer ve getiri yüzdesini hesaplar."
          example="Her ay 1.000 TL'yi 12 ay boyunca THYAO'ya yatırdığınızı varsayalım. Hesaplayıcı, fiyatın zaman içindeki dalgalanmasına göre toplam 12.000 TL'nin bugün ne kadar değere ulaştığını gösterir."
          onClose={() => setShowHelp(false)}
        />
      )}

      <div className="flex items-center gap-2">
        <Calculator className="w-4 h-4 text-[#F59E0B]" />
        <h4 className="text-xs font-bold text-white uppercase tracking-wide">Düzenli Yatırım (DCA) Simülasyonu</h4>
        <button
          onClick={() => setShowHelp(true)}
          title="Nasıl Kullanılır?"
          className="text-gray-500 hover:text-[#F59E0B] transition"
        >
          <HelpCircle className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] text-gray-500 uppercase font-semibold">Aylık Tutar (TL)</label>
          <input
            type="number"
            min={1}
            className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#F59E0B] rounded-lg px-3 py-2 text-white text-sm tabular-nums outline-none transition"
            value={monthlyAmount}
            onChange={(e) => setMonthlyAmount(Math.max(1, Number(e.target.value) || 0))}
          />
        </div>
        <div>
          <label className="text-[10px] text-gray-500 uppercase font-semibold">Süre (Ay)</label>
          <input
            type="number"
            min={1}
            max={60}
            className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#F59E0B] rounded-lg px-3 py-2 text-white text-sm tabular-nums outline-none transition"
            value={months}
            onChange={(e) => setMonths(Math.min(60, Math.max(1, Number(e.target.value) || 1)))}
          />
        </div>
      </div>

      <button
        onClick={handleRun}
        disabled={loading}
        className="w-full bg-[var(--brand)] hover:bg-[var(--brand-hover)] text-white font-bold text-xs py-2 rounded-lg transition disabled:opacity-50 flex items-center justify-center gap-1.5"
      >
        {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
        Simülasyonu Çalıştır
      </button>

      {result && (
        <div className="pt-2 border-t border-[#242B35]">
          {!result.available ? (
            <p className="text-[11px] text-gray-500">{result.message}</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-gray-500 text-[10px] uppercase">Toplam Yatırılan</span>
                <p className="text-base font-bold text-white tabular-nums">
                  {result.total_invested?.toLocaleString("tr-TR")} TL
                </p>
              </div>
              <div>
                <span className="text-gray-500 text-[10px] uppercase">Güncel Değer</span>
                <p className="text-base font-bold text-white tabular-nums">
                  {result.final_value?.toLocaleString("tr-TR")} TL
                </p>
              </div>
              <div className="col-span-2 flex items-center gap-1.5">
                {(result.profit_pct ?? 0) >= 0 ? (
                  <TrendingUp className="w-4 h-4 text-[#10B981]" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-[#F43F5E]" />
                )}
                <span className={`font-bold tabular-nums ${marketTextClass(result.profit_pct)}`}>
                  {result.profit?.toLocaleString("tr-TR")} TL ({(result.profit_pct ?? 0) > 0 ? "+" : ""}
                  {result.profit_pct?.toFixed(2)}%)
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
