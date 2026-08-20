"use client";

import React, { useEffect, useState } from "react";
import { Coins, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface Payment {
  pay_date: string;
  amount: number;
  year: number;
}

interface Data {
  symbol: string;
  company_name: string;
  payments: Payment[];
  yearly_totals: Record<string, number>;
  years_paid: number;
  last_payment_date: string | null;
  average_last_3y: number | null;
  trend: string | null;
}

const TREND_STYLE: Record<string, { color: string; Icon: React.ElementType }> = {
  "Artıyor": { color: "#10B981", Icon: TrendingUp },
  "Azalıyor": { color: "#F43F5E", Icon: TrendingDown },
  "Değişken": { color: "#F59E0B", Icon: Minus },
};

/**
 * Temettü ödeme geçmişi. Katılım finansı odaklı bu uygulamada temettü merkezi
 * bir kavram olduğu için yalnızca güncel verim değil, şirketin düzenli ödeyip
 * ödemediği ve tutarın büyüyüp büyümediği de gösterilir.
 */
export default function DividendHistoryPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/dividend-history`);
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Temettü geçmişi alınamadı:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [symbol]);

  if (!data || data.payments.length === 0) return null;

  // Yıllar azalan sırada; devam eden yıl da gösterilir ama trendde kullanılmaz.
  const years = Object.keys(data.yearly_totals).sort().reverse().slice(0, 6);
  const maxTotal = Math.max(...years.map((y) => data.yearly_totals[y]), 0.0001);
  const currentYear = new Date().getFullYear();
  const trendStyle = data.trend ? TREND_STYLE[data.trend] : null;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-lg p-3 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Coins className="w-3.5 h-3.5 text-[#F59E0B]" />
          <p className="text-[9px] text-gray-500 uppercase font-bold">Temettü Geçmişi</p>
        </div>
        {trendStyle && (
          <span
            className="text-[10px] font-bold flex items-center gap-1"
            style={{ color: trendStyle.color }}
          >
            <trendStyle.Icon className="w-3 h-3" />
            {data.trend}
          </span>
        )}
      </div>

      {/* Yıl bazında toplam — bir yılda birden fazla taksit olabildiği için
          tek tek ödeme yerine yıllık toplam gösterilir. */}
      <div className="space-y-1.5">
        {years.map((y) => {
          const total = data.yearly_totals[y];
          const incomplete = Number(y) === currentYear;
          return (
            <div key={y} className="flex items-center gap-2">
              <span className="text-[10px] text-gray-500 w-9 shrink-0 tabular-nums">{y}</span>
              <div className="flex-1 h-2 rounded-full bg-[#0B0E14] overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${(total / maxTotal) * 100}%`,
                    backgroundColor: incomplete ? "#8A99AD" : "#F59E0B",
                  }}
                />
              </div>
              <span className="text-[10px] text-gray-300 tabular-nums w-16 text-right shrink-0">
                {total.toLocaleString("tr-TR", { maximumFractionDigits: 2 })} TL
              </span>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-2 pt-1 border-t border-[#242B35]">
        <div>
          <p className="text-[9px] text-gray-500 uppercase font-bold">Ödeme Yapılan Yıl</p>
          <p className="text-xs font-bold text-white tabular-nums mt-0.5">{data.years_paid} yıl</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-500 uppercase font-bold">Son 3 Yıl Ort.</p>
          <p className="text-xs font-bold text-white tabular-nums mt-0.5">
            {data.average_last_3y !== null
              ? `${data.average_last_3y.toLocaleString("tr-TR", { maximumFractionDigits: 2 })} TL`
              : "—"}
          </p>
        </div>
      </div>

      <p className="text-[9px] text-gray-600">
        Hisse başına brüt tutarlar. Yıllık toplamlardır — bir şirket aynı yıl birden
        fazla taksit ödeyebilir. İçinde bulunulan yıl henüz tamamlanmadığı için gri
        gösterilir ve trend hesabına katılmaz. Geçmiş ödeme geleceği garanti etmez.
      </p>
    </div>
  );
}
