"use client";

import React from "react";
import { ShieldCheck, AlertTriangle, Info } from "lucide-react";

interface Props {
  debtRatio?: number | null;
  assetRatio?: number | null;
  threshold?: number;
  detail?: string | null;
  checkedAt?: string | null;
}

/**
 * Katılım ön taramasının GEREKÇESİNİ gösterir.
 *
 * Katılım Endeksi yalnızca üyelik listesini yayımlar; bir hissenin ölçütlere ne
 * kadar yaklaştığını göstermez. Kullanıcı bu yüzden bir hissenin endeksten
 * çıkacağını ancak çıktıktan sonra öğrenir. Burada iki oran, sınıra uzaklığıyla
 * birlikte gösterilir.
 */
function OranCubugu({ label, value, threshold }: { label: string; value: number | null | undefined; threshold: number }) {
  if (value === null || value === undefined) {
    return (
      <div>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-[10px] text-gray-500">{label}</span>
          <span className="text-[11px] text-gray-600">hesaplanamadı</span>
        </div>
        <div className="h-1.5 rounded-full bg-[#0B0E14] mt-1" />
      </div>
    );
  }

  // Çubuk sınırı biraz aşacak yer bırakır; aksi halde %40 ile %90 aynı görünürdü.
  const olcek = threshold * 1.5;
  const genislik = Math.min(100, (value / olcek) * 100);
  const asildi = value >= threshold;
  const yakin = !asildi && value >= threshold * 0.85;
  const renk = asildi ? "#F43F5E" : yakin ? "#F59E0B" : "#10B981";

  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] text-gray-500">{label}</span>
        <span className="text-[11px] font-bold tabular-nums" style={{ color: renk }}>
          %{value.toLocaleString("tr-TR", { maximumFractionDigits: 1 })}
        </span>
      </div>
      <div className="relative h-1.5 rounded-full bg-[#0B0E14] mt-1 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${genislik}%`, backgroundColor: renk }} />
        {/* Sınır çizgisi — oranın nereye göre okunacağı görünür olmalı. */}
        <div
          className="absolute top-0 bottom-0 w-px bg-gray-500"
          style={{ left: `${(threshold / olcek) * 100}%` }}
          title={`Sınır %${threshold}`}
        />
      </div>
    </div>
  );
}

export default function KatilimScreenPanel({
  debtRatio,
  assetRatio,
  threshold = 33,
  detail,
  checkedAt,
}: Props) {
  // Hiç tarama yapılmamışsa panel gösterilmez.
  if (debtRatio === null || debtRatio === undefined) {
    if (!detail) return null;
  }

  const uyariVar = (detail || "").includes("Sınıra yaklaşıyor");

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3 space-y-3">
      <div className="flex items-center gap-2">
        <ShieldCheck className="w-3.5 h-3.5 text-[#4A87C7]" />
        <p className="text-[9px] text-gray-500 uppercase font-bold">Katılım Ön Taraması</p>
      </div>

      <div className="space-y-2.5">
        <OranCubugu label="Finansal borç / toplam varlık" value={debtRatio} threshold={threshold} />
        <OranCubugu label="Nakit ve finansal yatırımlar / toplam varlık" value={assetRatio} threshold={threshold} />
      </div>

      {detail && (
        <p
          className={`text-[10px] leading-relaxed flex items-start gap-1.5 ${
            uyariVar ? "text-[#F59E0B]" : "text-gray-400"
          }`}
        >
          {uyariVar && <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />}
          <span>{detail}</span>
        </p>
      )}

      <p className="text-[9px] text-gray-600 leading-relaxed flex items-start gap-1.5 border-t border-[#242B35] pt-2">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        <span>
          Bu oranlar <strong>bilgi amaçlıdır</strong>, uygunluk kararını belirlemez —
          rozetteki karar endeks kaydından gelir. Hesap üç yerde eksik kalıyor:
          bilançodaki nakdin yalnızca getirili kısmı ayrıştırılamıyor, holdinglerin
          iştirak yapısı görülemiyor ve &quot;uygun olmayan gelir / toplam gelir&quot;
          ölçütü yalnızca KAP dipnotlarında bulunduğu için hiç hesaplanamıyor.
          {checkedAt && (
            <> Son hesaplama: {new Date(checkedAt).toLocaleDateString("tr-TR")}.</>
          )}
        </span>
      </p>
    </div>
  );
}
