"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Calculator, Info, AlertTriangle } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

const RISK_SECENEKLERI = [0.5, 1, 2, 3, 5];

const fmt = (v: number) =>
  v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function RiskCalculatorPage() {
  const { token } = useAuth();
  const [portfoyDegeri, setPortfoyDegeri] = useState("100000");
  const [riskYuzdesi, setRiskYuzdesi] = useState(1);
  const [girisFiyati, setGirisFiyati] = useState("");
  const [stopFiyati, setStopFiyati] = useState("");

  // Kullanıcı girişliyse gerçek portföy değeri otomatik doldurulur -- elle
  // yazmak zorunda kalmasın, ama isterse yine de değiştirebilir.
  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/portfolio`, { headers: { Authorization: `Bearer ${token}` } });
        if (res.ok) {
          const data = await res.json();
          setPortfoyDegeri(String(Math.round(data.total_portfolio_value)));
        }
      } catch {
        // sessizce yoksay -- kullanıcı elle girebilir
      }
    })();
  }, [token]);

  const sonuc = useMemo(() => {
    const portfoy = Number.parseFloat(portfoyDegeri);
    const giris = Number.parseFloat(girisFiyati);
    const stop = Number.parseFloat(stopFiyati);

    if (!Number.isFinite(portfoy) || portfoy <= 0) return null;
    if (!Number.isFinite(giris) || giris <= 0) return null;
    if (!Number.isFinite(stop) || stop <= 0) return null;
    if (giris === stop) return null;

    const fiyatBasinaRisk = Math.abs(giris - stop);
    const riskeAtilanTutar = portfoy * (riskYuzdesi / 100);
    const onerilenAdet = riskeAtilanTutar / fiyatBasinaRisk;
    const toplamPozisyonTutari = onerilenAdet * giris;
    const portfoyYuzdesi = (toplamPozisyonTutari / portfoy) * 100;
    const stopUzaklikPct = (fiyatBasinaRisk / giris) * 100;
    const yonTakip = stop < giris ? "AL (uzun)" : "SAT (kısa)";

    return {
      fiyatBasinaRisk, riskeAtilanTutar, onerilenAdet, toplamPozisyonTutari,
      portfoyYuzdesi, stopUzaklikPct, yonTakip,
      cokBuyuk: portfoyYuzdesi > 100,
    };
  }, [portfoyDegeri, girisFiyati, stopFiyati, riskYuzdesi]);

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Calculator className="w-5 h-5 text-[#F59E0B]" /> Pozisyon Büyüklüğü Hesaplayıcı
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          &quot;Portföyümün en fazla %X&apos;ini bu işlemde riske atmak istiyorum&quot; disipliniyle,
          stop-loss mesafene göre kaç adet almanız gerektiğini hesaplar.
        </p>
      </div>

      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-4">
        <div>
          <label className="block text-[11px] font-semibold text-gray-400 mb-1.5">
            Toplam Portföy Değeri (TL)
          </label>
          <input
            type="number" inputMode="decimal" min={0}
            value={portfoyDegeri}
            onChange={(e) => setPortfoyDegeri(e.target.value)}
            className="w-full min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm tabular-nums focus:outline-none focus:border-[#F59E0B]"
          />
        </div>

        <div>
          <label className="block text-[11px] font-semibold text-gray-400 mb-1.5">
            Bu İşlemde Riske Edilecek Portföy Yüzdesi
          </label>
          <div className="flex items-center gap-1 bg-[#0B0E14] border border-[#242B35] rounded-lg p-1">
            {RISK_SECENEKLERI.map((r) => (
              <button
                key={r}
                onClick={() => setRiskYuzdesi(r)}
                className={`flex-1 min-h-[36px] text-[11px] font-semibold rounded-md transition ${
                  riskYuzdesi === r ? "bg-[#242B35] text-white" : "text-gray-500 hover:text-gray-300"
                }`}
              >
                %{r}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-semibold text-gray-400 mb-1.5">Giriş Fiyatı (TL)</label>
            <input
              type="number" inputMode="decimal" min={0} step="0.01"
              value={girisFiyati}
              onChange={(e) => setGirisFiyati(e.target.value)}
              placeholder="Örn. 100.00"
              className="w-full min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm tabular-nums focus:outline-none focus:border-[#F59E0B]"
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-gray-400 mb-1.5">Stop-Loss Fiyatı (TL)</label>
            <input
              type="number" inputMode="decimal" min={0} step="0.01"
              value={stopFiyati}
              onChange={(e) => setStopFiyati(e.target.value)}
              placeholder="Örn. 95.00"
              className="w-full min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm tabular-nums focus:outline-none focus:border-[#F59E0B]"
            />
          </div>
        </div>
      </div>

      {sonuc && (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Yön</span>
            <span className="text-sm font-bold text-white">{sonuc.yonTakip}</span>
          </div>

          <div className="rounded-lg bg-[#F59E0B]/10 border border-[#F59E0B]/30 p-4 text-center">
            <p className="text-[10px] text-gray-400 uppercase font-semibold mb-1">Önerilen Adet</p>
            <p className="text-2xl font-bold text-[#F59E0B] tabular-nums">
              {sonuc.onerilenAdet.toLocaleString("tr-TR", { maximumFractionDigits: 2 })}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
              <p className="text-[10px] text-gray-500 uppercase font-semibold">Riske Edilen Tutar</p>
              <p className="text-sm font-bold text-white tabular-nums">{fmt(sonuc.riskeAtilanTutar)} TL</p>
            </div>
            <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
              <p className="text-[10px] text-gray-500 uppercase font-semibold">Toplam Pozisyon Tutarı</p>
              <p className="text-sm font-bold text-white tabular-nums">{fmt(sonuc.toplamPozisyonTutari)} TL</p>
            </div>
            <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
              <p className="text-[10px] text-gray-500 uppercase font-semibold">Fiyat Başına Risk</p>
              <p className="text-sm font-bold text-white tabular-nums">{fmt(sonuc.fiyatBasinaRisk)} TL</p>
            </div>
            <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
              <p className="text-[10px] text-gray-500 uppercase font-semibold">Stop Uzaklığı</p>
              <p className="text-sm font-bold text-white tabular-nums">%{sonuc.stopUzaklikPct.toFixed(2)}</p>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs pt-1">
            <span className="text-gray-500">Portföyünün yüzdesi</span>
            <span className={`font-bold tabular-nums ${sonuc.cokBuyuk ? "text-[#F43F5E]" : "text-white"}`}>
              %{sonuc.portfoyYuzdesi.toFixed(1)}
            </span>
          </div>

          {sonuc.cokBuyuk && (
            <p className="text-[11px] text-[#F43F5E] flex items-start gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              Önerilen pozisyon tutarı portföy değerinden büyük — stop mesafen çok dar
              veya risk yüzden bu portföy için yüksek olabilir.
            </p>
          )}
        </div>
      )}

      <p className="text-[10px] text-gray-600 flex items-start gap-1.5">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        <span>
          Yöntem: Riske Edilen Tutar = Portföy × Risk%. Önerilen Adet = Riske Edilen Tutar /
          |Giriş − Stop|. Bu, deneyimli trader&apos;ların pozisyon büyüklüğü belirlerken kullandığı
          standart sabit-yüzde risk yöntemidir. Yatırım tavsiyesi değildir.
        </span>
      </p>
    </div>
  );
}
