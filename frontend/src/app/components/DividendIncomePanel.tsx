"use client";

import React, { useEffect, useState } from "react";
import { Coins, Info } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface DividendItem {
  symbol: string;
  company_name: string;
  quantity: number;
  current_value: number;
  dividend_yield: number | null;
  annual_income: number | null;
  yield_on_cost: number | null;
  last_dividend_date: string | null;
}

interface DividendData {
  total_annual_income: number;
  monthly_average: number;
  portfolio_value: number;
  portfolio_yield: number | null;
  covered_positions: number;
  total_positions: number;
  items: DividendItem[];
}

const fmt = (v: number) =>
  v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/**
 * Portföyün beklenen yıllık temettü geliri.
 *
 * "Maliyete göre verim" ayrıca gösterilir: uzun vadeli yatırımcı için asıl
 * anlamlı olan, hisseyi bugün alsa elde edeceği verim değil, kendi maliyetine
 * göre elde ettiği verimdir.
 */
export default function DividendIncomePanel({ refreshKey }: { refreshKey?: number }) {
  const { token } = useAuth();
  const [data, setData] = useState<DividendData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/portfolio/dividends`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Temettü verisi alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [token, refreshKey]);

  if (loading || !data || data.total_positions === 0) return null;

  const withIncome = data.items.filter((i) => (i.annual_income ?? 0) > 0);

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Coins className="w-4 h-4 text-[#F59E0B]" />
        <h3 className="text-xs font-bold text-white uppercase tracking-wide">
          Beklenen Temettü Geliri
        </h3>
      </div>

      {withIncome.length === 0 ? (
        <p className="text-[11px] text-gray-500">
          Portföyünüzdeki hisseler için henüz temettü verisi yok. Bilanço analizi
          tazelendikçe burada görünecektir.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <p className="text-[10px] text-gray-500 mb-0.5">Yıllık</p>
              <p className="text-lg font-bold text-[#F59E0B] tabular-nums">
                {fmt(data.total_annual_income)} TL
              </p>
            </div>
            <div>
              <p className="text-[10px] text-gray-500 mb-0.5">Aylık ortalama</p>
              <p className="text-lg font-bold text-white tabular-nums">
                {fmt(data.monthly_average)} TL
              </p>
            </div>
            <div>
              <p className="text-[10px] text-gray-500 mb-0.5">Portföy verimi</p>
              <p className="text-lg font-bold text-white tabular-nums">
                {data.portfolio_yield === null ? "—" : `%${data.portfolio_yield.toFixed(2)}`}
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs min-w-[420px]">
              <thead>
                <tr className="border-b border-[#242B35] text-gray-500">
                  <th className="pb-2 pr-3 font-semibold">Hisse</th>
                  <th className="pb-2 px-3 font-semibold text-right">Verim</th>
                  <th className="pb-2 px-3 font-semibold text-right">Maliyete Göre</th>
                  <th className="pb-2 pl-3 font-semibold text-right">Yıllık Gelir</th>
                </tr>
              </thead>
              <tbody>
                {withIncome.map((i) => (
                  <tr key={i.symbol} className="border-b border-[#242B35]/50">
                    <td className="py-2 pr-3 font-bold text-white">{i.symbol}</td>
                    <td className="py-2 px-3 text-right tabular-nums text-gray-400">
                      %{i.dividend_yield?.toFixed(2)}
                    </td>
                    <td className="py-2 px-3 text-right tabular-nums font-semibold text-[#10B981]">
                      {i.yield_on_cost === null ? "—" : `%${i.yield_on_cost.toFixed(2)}`}
                    </td>
                    <td className="py-2 pl-3 text-right tabular-nums font-semibold text-white">
                      {fmt(i.annual_income as number)} TL
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.covered_positions < data.total_positions && (
            <p className="text-[10px] text-gray-600">
              {data.total_positions} pozisyondan {data.covered_positions} tanesinde temettü
              verisi var; diğerleri hesaba katılmadı.
            </p>
          )}
        </>
      )}

      <p className="text-[10px] text-gray-600 flex items-start gap-1.5 border-t border-[#242B35] pt-3">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        <span>
          Bu bir <strong>tahmindir</strong>: son bilinen temettü verimi üzerinden
          hesaplanır. Şirketlerin gelecekte aynı temettüyü ödeyeceği garanti değildir,
          temettü kesilebilir veya artabilir. Yatırım tavsiyesi değildir.
        </span>
      </p>
    </div>
  );
}
