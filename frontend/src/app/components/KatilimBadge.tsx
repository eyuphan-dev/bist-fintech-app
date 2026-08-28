"use client";

import React, { useState } from "react";
import { CheckCircle2, XCircle, Info, HelpCircle, AlertTriangle } from "lucide-react";

/** KAP "Katılım Finansı İlkeleri Bilgi Formu" — şirketin kendi resmi beyanı. */
export interface KapKatilimVerisi {
  gelir_pct: number | null;
  varlik_pct: number | null;
  borc_pct: number | null;
  donem: string | null;
  url: string | null;
}

interface KatilimBadgeProps {
  isCompliant: boolean;
  /**
   * @deprecated Uydurma veriydi — kullanılmıyor, geriye dönük uyum için duruyor.
   * Gerçek oranlar `kap` prop'undan gelir.
   */
  purificationRate?: number;
  nonComplianceReason?: string | null;
  size?: "sm" | "md";
  /** 'UYGUN' | 'UYGUN_DEGIL' | 'BELIRSIZ'. Verilmezse isCompliant kullanılır. */
  status?: string | null;
  /** KAP resmi beyanı; yoksa oran bölümü hiç gösterilmez. */
  kap?: KapKatilimVerisi | null;
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
/** KAP beyanındaki oranlardan herhangi biri resmi eşiği aşıyor mu. */
function esikAsiliyor(kap: KapKatilimVerisi): boolean {
  return (
    (kap.gelir_pct !== null && kap.gelir_pct > 5) ||
    (kap.varlik_pct !== null && kap.varlik_pct > 33) ||
    (kap.borc_pct !== null && kap.borc_pct > 33)
  );
}

/** Tek bir oran satırı: değer, eşik ve eşiğin altında mı üstünde mi. */
function OranSatiri({ etiket, deger, esik }: { etiket: string; deger: number | null; esik: number }) {
  if (deger === null) return null;
  const asiyor = deger > esik;
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="text-[10px] text-gray-400">{etiket}</dt>
      <dd className="flex items-baseline gap-1">
        <span className={`text-xs font-bold tabular-nums ${asiyor ? "text-[#F43F5E]" : "text-[#10B981]"}`}>
          %{deger.toFixed(2)}
        </span>
        <span className="text-[9px] text-gray-600 tabular-nums">/ %{esik}</span>
      </dd>
    </div>
  );
}

export default function KatilimBadge({
  isCompliant,
  nonComplianceReason,
  size = "md",
  status,
  kap = null,
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
            className="absolute z-40 top-full mt-2 left-0 w-64 bg-[#151921] border border-[#242B35] rounded-xl p-3"
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
            className="absolute z-40 top-full mt-2 left-0 w-64 bg-[#151921] border border-[#242B35] rounded-xl p-3"
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
          className="absolute z-40 top-full mt-2 left-0 w-64 bg-[#151921] border border-[#242B35] rounded-xl p-3"
          onMouseLeave={() => setShowPopover(false)}
        >
          {/* ÖNEMLİ: burada eskiden UYDURMA bir "arınma oranı" gösteriliyor ve
              kullanıcıya "kazancınızın bu kadarını bağışlayın" deniyordu.
              Sayı elle yazılmış bir yer tutucuydu. Artık yalnızca KAP'a
              bildirilen resmi beyan gösterilir; beyan yoksa HİÇBİR ORAN
              GÖSTERİLMEZ. */}
          <div className="flex items-start gap-2">
            <Info className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />
            <div className="min-w-0">
              {kap && (kap.gelir_pct !== null || kap.varlik_pct !== null || kap.borc_pct !== null) ? (
                <>
                  <p className="text-[11px] font-semibold text-white">
                    Katılım Finansı İlkeleri Bilgi Formu
                  </p>
                  <p className="text-[10px] text-gray-500 mb-1.5">
                    Şirketin KAP&apos;a bildirdiği resmi beyan
                    {kap.donem ? ` · ${kap.donem}` : ""}
                  </p>
                  <dl className="space-y-1">
                    <OranSatiri etiket="Uygun olmayan gelir" deger={kap.gelir_pct} esik={5} />
                    <OranSatiri etiket="Uygun olmayan varlık" deger={kap.varlik_pct} esik={33} />
                    <OranSatiri etiket="Uygun olmayan borç" deger={kap.borc_pct} esik={33} />
                  </dl>

                  {/* ÇELİŞKİ UYARISI. Hisse "uygun" işaretli ama şirketin KENDİ
                      resmi beyanı bir eşiği aşıyorsa kullanıcı bunu bilmeli.
                      Ölçüldü: beyanı olan 38 hissenin 9'unda bu çelişki var
                      (uyum %76). Durumu otomatik değiştirmiyoruz — endeksin
                      kendi yöntemi ve dönem farkları olabilir — ama çelişkiyi
                      gizlemek de doğru olmaz. Karar kullanıcının.

                      Ters yönde hiç çelişki YOK: "uygun değil" işaretli 4
                      hissenin dördünde de beyan eşiği aşıyor. */}
                  {esikAsiliyor(kap) && (
                    <div className="mt-2 flex items-start gap-1.5 rounded-md bg-[#F59E0B]/10 border border-[#F59E0B]/25 px-2 py-1.5">
                      <AlertTriangle className="w-3 h-3 text-[#F59E0B] shrink-0 mt-0.5" />
                      <p className="text-[10px] text-[#F59E0B] leading-relaxed">
                        Bu hisse &quot;uygun&quot; olarak işaretli, ancak şirketin KAP&apos;a
                        bildirdiği oranlardan en az biri eşiği aşıyor. Kendi
                        değerlendirmenizi yapın.
                      </p>
                    </div>
                  )}
                  <p className="text-[10px] text-gray-400 mt-2 leading-relaxed">
                    Uygun olmayan gelir oranı, kazancınızdan arındırılması önerilen
                    kısmı gösterir.
                  </p>
                  {kap.url && (
                    <a
                      href={kap.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-[#10B981] hover:underline mt-1.5 inline-block"
                    >
                      KAP bildirimini aç →
                    </a>
                  )}
                </>
              ) : (
                <>
                  <p className="text-[11px] font-semibold text-white">Oran verisi yok</p>
                  <p className="text-[10px] text-gray-400 mt-1 leading-relaxed">
                    Bu şirket için KAP&apos;a bildirilmiş Katılım Finansı İlkeleri Bilgi
                    Formu bulunamadı. Uydurma bir oran göstermek yerine boş bırakıyoruz.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
