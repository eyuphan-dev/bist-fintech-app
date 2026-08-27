"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ShieldCheck, RefreshCw, Info } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Pozisyon {
  symbol: string;
  company_name: string | null;
  value: number;
  weight_pct: number;
  katilim_status: string | null;
  kap_gelir_pct: number | null;
  kap_donem: string | null;
  kap_url: string | null;
}

interface Karne {
  total_value: number;
  uygun_value: number;
  uygun_pct: number;
  uygun_degil_value: number;
  uygun_degil_pct: number;
  belirsiz_value: number;
  belirsiz_pct: number;
  kap_kapsam_pct: number;
  agirlikli_arindirma_pct: number | null;
  positions: Pozisyon[];
}

/**
 * Portföyün katılım (faizsiz) uyum karnesi.
 *
 * Uygulamanın ayırt edici özelliği katılım odağı ama kullanıcı portföyünün
 * NE KADARININ uygun olduğunu hiçbir yerde göremiyordu — yalnızca hisse
 * bazında rozet vardı.
 */
export default function KatilimKarnesi({ refreshKey }: { refreshKey?: number }) {
  const { token } = useAuth();
  const [karne, setKarne] = useState<Karne | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [detayAcik, setDetayAcik] = useState(false);

  const getir = useCallback(async () => {
    if (!token) return;
    setYukleniyor(true);
    try {
      const res = await fetch(`${API_BASE}/portfolio/katilim`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setKarne(await res.json());
    } catch {
      /* sessizce geç: karne kritik değil, portföyün kendisi zaten görünüyor */
    } finally {
      setYukleniyor(false);
    }
  }, [token]);

  useEffect(() => {
    getir();
  }, [getir, refreshKey]);

  if (!token) return null;

  if (yukleniyor && !karne) {
    return (
      <div className="flex items-center justify-center py-8 text-gray-500 text-xs">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
        Katılım karnesi hesaplanıyor...
      </div>
    );
  }

  if (!karne || karne.total_value <= 0) {
    return (
      <p className="text-xs text-gray-500 py-6 text-center">
        Katılım karnesi için portföyünüzde en az bir hisse olmalı.
      </p>
    );
  }

  const dilimler = [
    { etiket: "Uygun", pct: karne.uygun_pct, deger: karne.uygun_value, renk: "#10B981" },
    { etiket: "Uygun değil", pct: karne.uygun_degil_pct, deger: karne.uygun_degil_value, renk: "#F43F5E" },
    { etiket: "Değerlendirilmedi", pct: karne.belirsiz_pct, deger: karne.belirsiz_value, renk: "#6B7280" },
  ].filter((d) => d.pct > 0);

  const tl = (n: number) =>
    n.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-[#10B981]" /> Katılım Uyum Karnesi
        </h2>
        <button
          onClick={getir}
          aria-label="Karneyi yenile"
          className="text-gray-500 hover:text-white transition p-2 -m-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${yukleniyor ? "animate-spin" : ""}`} />
        </button>
      </div>

      {/* Tek çubukta dağılım */}
      <div className="flex h-2.5 rounded-full overflow-hidden bg-[#242B35]">
        {dilimler.map((d) => (
          <div
            key={d.etiket}
            style={{ width: `${d.pct}%`, backgroundColor: d.renk }}
            title={`${d.etiket}: %${d.pct}`}
          />
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2">
        {dilimler.map((d) => (
          <div key={d.etiket} className="bg-[#151921] border border-[#242B35] rounded-lg px-3 py-2">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: d.renk }} />
              <span className="text-[10px] text-gray-400 truncate">{d.etiket}</span>
            </div>
            <p className="text-base font-bold text-white tabular-nums mt-0.5">%{d.pct.toFixed(1)}</p>
            <p className="text-[10px] text-gray-600 tabular-nums">{tl(d.deger)} TL</p>
          </div>
        ))}
      </div>

      {/* Arındırma oranı — KAPSAM İLE BİRLİKTE.
          Kapsamı ayrıca göstermezsek kullanıcı bu oranın tüm portföyü temsil
          ettiğini sanır. Üretimde 165 hissenin 36'sında KAP beyanı var, yani
          çoğu portföyde kapsam kısmi olacak ve bunu gizlemek yanlış olur. */}
      <div className="bg-[#151921] border border-[#242B35] rounded-lg px-3 py-2.5">
        <div className="flex items-start gap-2">
          <Info className="w-3.5 h-3.5 text-[#10B981] shrink-0 mt-0.5" />
          <div className="min-w-0">
            {karne.agirlikli_arindirma_pct !== null ? (
              <>
                <p className="text-[11px] text-gray-400">
                  Ağırlıklı arındırma oranı
                  <span className="text-sm font-bold text-white tabular-nums ml-1.5">
                    %{karne.agirlikli_arindirma_pct.toFixed(2)}
                  </span>
                </p>
                <p className="text-[10px] text-gray-500 mt-1 leading-relaxed">
                  Şirketlerin KAP&apos;a bildirdiği &quot;uygun olmayan gelir&quot; oranlarının,
                  değere göre ağırlıklı ortalaması. Bu oran portföyünüzün{" "}
                  <strong className="text-gray-300">%{karne.kap_kapsam_pct.toFixed(1)}</strong>&apos;ini
                  kapsıyor — kalan kısım için şirketler henüz beyan vermemiş.
                </p>
              </>
            ) : (
              <p className="text-[10px] text-gray-500 leading-relaxed">
                Portföyünüzdeki hiçbir şirketin KAP&apos;a bildirilmiş Katılım Finansı
                İlkeleri Bilgi Formu bulunamadı. Uydurma bir oran göstermek yerine
                boş bırakıyoruz.
              </p>
            )}
          </div>
        </div>
      </div>

      <button
        onClick={() => setDetayAcik((v) => !v)}
        className="text-[11px] font-semibold text-gray-400 hover:text-white transition min-h-[44px] w-full text-left"
      >
        {detayAcik ? "Pozisyon dökümünü gizle" : `Pozisyon dökümü (${karne.positions.length})`}
      </button>

      {detayAcik && (
        <ul className="divide-y divide-[#242B35] border border-[#242B35] rounded-xl overflow-hidden">
          {karne.positions.map((p) => (
            <li key={p.symbol} className="bg-[#151921] px-3 py-2.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <Link
                  href={`/hisse/${p.symbol}`}
                  className="text-sm font-bold text-white hover:text-[#10B981] transition"
                >
                  {p.symbol}
                </Link>
                <p className="text-[10px] text-gray-500 tabular-nums">
                  %{p.weight_pct.toFixed(1)} · {tl(p.value)} TL
                </p>
              </div>
              <div className="text-right shrink-0">
                <span
                  className={`text-[10px] font-bold ${
                    p.katilim_status === "UYGUN"
                      ? "text-[#10B981]"
                      : p.katilim_status === "UYGUN_DEGIL"
                        ? "text-[#F43F5E]"
                        : "text-gray-500"
                  }`}
                >
                  {p.katilim_status === "UYGUN"
                    ? "Uygun"
                    : p.katilim_status === "UYGUN_DEGIL"
                      ? "Uygun değil"
                      : "Değerlendirilmedi"}
                </span>
                {p.kap_gelir_pct !== null && (
                  <p className="text-[10px] text-gray-500 tabular-nums">
                    KAP gelir %{p.kap_gelir_pct.toFixed(2)}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
