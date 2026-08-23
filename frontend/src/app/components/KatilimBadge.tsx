"use client";

import React, { useState } from "react";
import { CheckCircle2, XCircle, Info, HelpCircle } from "lucide-react";

interface KatilimBadgeProps {
  isCompliant: boolean;
  purificationRate: number;
  nonComplianceReason?: string | null;
  size?: "sm" | "md";
  /** 'UYGUN' | 'UYGUN_DEGIL' | 'BELIRSIZ'. Verilmezse isCompliant kullanılır. */
  status?: string | null;
}

/**
 * Katılım Endeksi (Helal Finans) uygunluk rozeti — ÜÇ durumlu.
 *
 * Uygun ise yeşil rozet + tıklanınca arınma oranı; uygun değilse kırmızı rozet
 * + gerekçe. ÜÇÜNCÜ DURUM: katalog 43'ten 165 hisseye çıkarıldığında yeni
 * hisseler için elle küratörlü katılım verisi yoktu. Bunları kırmızı "UYGUN
 * DEĞİL" göstermek, bilmediğimiz bir şeyi iddia etmek olurdu — bu yüzden nötr
 * gri "değerlendirilmedi" rozeti gösterilir.
 */
export default function KatilimBadge({
  isCompliant,
  purificationRate,
  nonComplianceReason,
  size = "md",
  status,
}: KatilimBadgeProps) {
  const [showPopover, setShowPopover] = useState(false);

  const sizeClasses = size === "sm" ? "text-[10px] px-1.5 py-0.5" : "text-xs px-2 py-1";

  if (status === "BELIRSIZ") {
    return (
      <div className="relative inline-block">
        <button
          onClick={() => setShowPopover((v) => !v)}
          type="button"
          className={`inline-flex items-center gap-1 rounded-md font-bold uppercase tracking-wide bg-[#8A99AD]/10 text-[#8A99AD] border border-[#8A99AD]/25 ${sizeClasses}`}
        >
          <HelpCircle className="w-3 h-3" />
          DEĞERLENDİRİLMEDİ
        </button>

        {showPopover && (
          <div
            className="absolute z-40 top-full mt-2 left-0 w-64 bg-[#151921] border border-[#242B35] rounded-lg shadow-xl p-3"
            onMouseLeave={() => setShowPopover(false)}
          >
            <p className="text-[11px] text-gray-300 leading-relaxed">
              Bu hissenin katılım endeksi uygunluğu henüz değerlendirilmedi.
              &quot;Uygun değil&quot; anlamına <strong>gelmez</strong> — sadece
              elimizde doğrulanmış bir veri yok.
            </p>
          </div>
        )}
      </div>
    );
  }

  if (!isCompliant) {
    return (
      <div className="relative inline-block">
        <button
          onClick={() => setShowPopover((v) => !v)}
          className={`inline-flex items-center gap-1 rounded-md font-bold uppercase tracking-wide bg-[#F43F5E]/10 text-[#F43F5E] border border-[#F43F5E]/25 ${sizeClasses}`}
        >
          <XCircle className="w-3 h-3" />
          ✕ UYGUN DEĞİL
        </button>

        {showPopover && (
          <div
            className="absolute z-40 top-full mt-2 left-0 w-64 bg-[#151921] border border-[#242B35] rounded-lg shadow-xl p-3"
            onMouseLeave={() => setShowPopover(false)}
          >
            <p className="text-[11px] text-gray-300 leading-relaxed">
              {nonComplianceReason || "Bu hisse, faaliyet konusu veya finansal oranları nedeniyle Katılım Endeksi kriterlerini karşılamamaktadır."}
            </p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setShowPopover((v) => !v)}
        className={`inline-flex items-center gap-1 rounded-md font-bold uppercase tracking-wide bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/25 ${sizeClasses}`}
      >
        <CheckCircle2 className="w-3 h-3" />
        ✓ KATILIM ENDEKSİNE UYGUN
      </button>

      {showPopover && (
        <div
          className="absolute z-40 top-full mt-2 left-0 w-64 bg-[#151921] border border-[#242B35] rounded-lg shadow-xl p-3"
          onMouseLeave={() => setShowPopover(false)}
        >
          <div className="flex items-start gap-2">
            <Info className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />
            <div>
              <p className="text-[11px] font-semibold text-white">Arınma (Purification) Oranı</p>
              <p className="text-lg font-bold text-[#F59E0B] tabular-nums mt-0.5">
                %{purificationRate.toFixed(2)}
              </p>
              <p className="text-[10px] text-gray-400 mt-1 leading-relaxed">
                Kazancınızın bu oranı, şirketin faizli/gayri helal gelir kalemlerinden
                arındırılması için hayır kurumuna bağışlanması önerilen kısımdır.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
