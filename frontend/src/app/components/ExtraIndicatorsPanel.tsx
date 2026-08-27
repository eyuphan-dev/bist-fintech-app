"use client";

import React, { useEffect, useState } from "react";
import { Activity, Info } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface Data {
  available: boolean;
  reason?: string | null;
  as_of?: string | null;
  bar_count?: number | null;
  stochastic_k?: number | null;
  stochastic_d?: number | null;
  adx?: number | null;
  obv?: number | null;
  obv_slope?: number | null;
}

/** 0-100 bandında konum çubuğu; aşırı bölgeler renklenir. */
function Bant({
  label,
  value,
  altEsik,
  ustEsik,
  altMetin,
  ustMetin,
  notrMetin,
}: {
  label: string;
  value: number | null | undefined;
  altEsik: number;
  ustEsik: number;
  altMetin: string;
  ustMetin: string;
  notrMetin: string;
}) {
  if (value === null || value === undefined) {
    return (
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-gray-500">{label}</span>
        <span className="text-[10px] text-gray-600">hesaplanamadı</span>
      </div>
    );
  }
  const dusuk = value <= altEsik;
  const yuksek = value >= ustEsik;
  const renk = yuksek ? "#F43F5E" : dusuk ? "#10B981" : "#8A99AD";
  const yorum = yuksek ? ustMetin : dusuk ? altMetin : notrMetin;

  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] text-gray-500">{label}</span>
        <span className="text-[11px] font-bold tabular-nums" style={{ color: renk }}>
          {value.toLocaleString("tr-TR", { maximumFractionDigits: 1 })}
        </span>
      </div>
      <div className="relative h-1.5 rounded-full bg-[#0B0E14] overflow-hidden">
        <div
          className="absolute top-0 bottom-0 w-1 rounded-full"
          style={{ left: `calc(${Math.min(100, Math.max(0, value))}% - 2px)`, backgroundColor: renk }}
        />
      </div>
      <p className="text-[9px]" style={{ color: renk }}>{yorum}</p>
    </div>
  );
}

/**
 * Stochastic, ADX ve OBV.
 *
 * Bu üçü mevcut RSI/MACD/SMA setinden AYRI bir veri kaynağı kullanır: gün içi
 * anlık fiyat kayıtlarında yüksek/düşük yoktur, Stochastic ve ADX ise tanımı
 * gereği bunlara ihtiyaç duyar. Günlük OHLCV barlarından hesaplanırlar.
 */
export default function ExtraIndicatorsPanel({ symbol }: { symbol: string }) {
  const [data, setData] = useState<Data | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/indicators`);
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Ek göstergeler alınamadı:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [symbol]);

  if (!data) return null;

  if (!data.available) {
    return (
      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <Activity className="w-4 h-4 text-[#F59E0B]" />
          <h4 className="text-xs font-bold text-white uppercase tracking-wide">Ek Göstergeler</h4>
        </div>
        <p className="text-[11px] text-gray-500">{data.reason}</p>
      </div>
    );
  }

  const adx = data.adx;
  const adxRenk = adx === null || adx === undefined ? "#8A99AD" : adx >= 25 ? "#10B981" : adx < 20 ? "#F59E0B" : "#8A99AD";
  const adxYorum =
    adx === null || adx === undefined
      ? "—"
      : adx >= 25
      ? "Güçlü trend var"
      : adx < 20
      ? "Yönsüz piyasa — kesişim sinyalleri güvenilmez"
      : "Trend zayıf/kararsız";

  const egim = data.obv_slope;
  const egimRenk = egim === null || egim === undefined ? "#8A99AD" : egim > 0.5 ? "#10B981" : egim < -0.5 ? "#F43F5E" : "#8A99AD";
  const egimYorum =
    egim === null || egim === undefined
      ? "—"
      : egim > 0.5
      ? "Hacim alış yönünde birikiyor"
      : egim < -0.5
      ? "Hacim satış yönünde birikiyor"
      : "Hacim yönsüz";

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#F59E0B]" />
          <h4 className="text-xs font-bold text-white uppercase tracking-wide">Ek Göstergeler</h4>
        </div>
        <span className="text-[9px] text-gray-600">günlük barlar</span>
      </div>

      <Bant
        label="Stochastic %K"
        value={data.stochastic_k}
        altEsik={20}
        ustEsik={80}
        altMetin="Aşırı satım bölgesinde"
        ustMetin="Aşırı alım bölgesinde"
        notrMetin="Bandın ortasında"
      />
      {data.stochastic_d !== null && data.stochastic_d !== undefined && (
        <p className="text-[9px] text-gray-600 -mt-1.5">
          %D (sinyal): {data.stochastic_d.toLocaleString("tr-TR", { maximumFractionDigits: 1 })}
        </p>
      )}

      <div className="grid grid-cols-2 gap-2 pt-1 border-t border-[#242B35]">
        <div>
          <p className="text-[9px] text-gray-500 uppercase font-bold">ADX (trend gücü)</p>
          <p className="text-sm font-bold tabular-nums mt-0.5" style={{ color: adxRenk }}>
            {adx !== null && adx !== undefined ? adx.toLocaleString("tr-TR", { maximumFractionDigits: 1 }) : "—"}
          </p>
          <p className="text-[9px] leading-snug mt-0.5" style={{ color: adxRenk }}>{adxYorum}</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-500 uppercase font-bold">OBV eğilimi</p>
          <p className="text-sm font-bold tabular-nums mt-0.5" style={{ color: egimRenk }}>
            {egim !== null && egim !== undefined ? (egim > 0 ? "+" : "") + egim.toLocaleString("tr-TR", { maximumFractionDigits: 2 }) : "—"}
          </p>
          <p className="text-[9px] leading-snug mt-0.5" style={{ color: egimRenk }}>{egimYorum}</p>
        </div>
      </div>

      <p className="text-[9px] text-gray-600 leading-relaxed flex items-start gap-1.5 border-t border-[#242B35] pt-2.5">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        <span>
          <strong>ADX yönü değil gücü ölçer</strong> — 20 altında piyasa yönsüzdür ve
          kesişim sinyalleri sık sık yanlış çıkar. <strong>OBV</strong> hacmin yönlü
          birikimidir; ham değeri anlamsız olduğu için son 20 günlük değişimi ortalama
          hacme bölünerek gösterilir. Fiyat yükselirken OBV yükselmiyorsa hareketin
          arkasında hacim yok demektir.
        </span>
      </p>
    </div>
  );
}
