"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Trash2, Copy, X, Users, TrendingUp, TrendingDown, Clock } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface MarketplaceItem {
  symbol: string;
  company_name: string;
  weight_pct: number;
  entry_price: number;
  current_price: number | null;
  getiri_pct: number | null;
}

interface MarketplaceBasket {
  id: number;
  name: string;
  description: string | null;
  owner_username: string;
  created_at: string;
  getiri_pct: number | null;
  kopya_sayisi: number;
  is_mine: boolean;
  items: MarketplaceItem[];
}

interface StockOption {
  symbol: string;
  company_name: string;
  current_price: number;
}

type Siralama = "getiri" | "populer" | "yeni";
type DraftRow = { symbol: string; weight: string };

const SIRALAMALAR: { id: Siralama; label: string; icon: React.ElementType }[] = [
  { id: "getiri", label: "En Çok Kazandıran", icon: TrendingUp },
  { id: "populer", label: "En Çok Kopyalanan", icon: Users },
  { id: "yeni", label: "En Yeni", icon: Clock },
];

const fmt = (n: number) => n.toLocaleString("tr-TR", { maximumFractionDigits: 2 });

function GetiriRozeti({ pct }: { pct: number | null }) {
  if (pct === null) return <span className="text-xs font-bold text-gray-500">—</span>;
  const pozitif = pct >= 0;
  return (
    <span className={`text-sm font-bold tabular-nums ${pozitif ? "text-[#10B981]" : "text-[#F43F5E]"}`}>
      {pozitif ? "+" : ""}{fmt(pct)}%
    </span>
  );
}

export default function MarketplacePanel() {
  const { token, bumpRefresh, refreshTrigger } = useAuth();
  const [baskets, setBaskets] = useState<MarketplaceBasket[]>([]);
  const [loading, setLoading] = useState(true);
  const [siralama, setSiralama] = useState<Siralama>("getiri");
  const [sadeceBenim, setSadeceBenim] = useState(false);
  const [sonuc, setSonuc] = useState<{ text: string; isError: boolean } | null>(null);

  const [kopyalanan, setKopyalanan] = useState<MarketplaceBasket | null>(null);
  const [tutar, setTutar] = useState("5000");
  const [kopyaYukleniyor, setKopyaYukleniyor] = useState(false);
  const [kopyaSonuc, setKopyaSonuc] = useState<{ text: string; isError: boolean } | null>(null);

  const [yayinAcik, setYayinAcik] = useState(false);
  const [stoklar, setStoklar] = useState<StockOption[]>([]);
  const [isim, setIsim] = useState("");
  const [aciklama, setAciklama] = useState("");
  const [satirlar, setSatirlar] = useState<DraftRow[]>([{ symbol: "", weight: "" }, { symbol: "", weight: "" }]);
  const [yayinYukleniyor, setYayinYukleniyor] = useState(false);
  const [yayinHata, setYayinHata] = useState<string | null>(null);
  const [silOnay, setSilOnay] = useState<number | null>(null);

  const yukle = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/marketplace?sort=${siralama}${sadeceBenim ? "&mine=true" : ""}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setBaskets(await res.json());
    } catch (err) {
      console.error("Pazaryeri alınamadı:", err);
    } finally {
      setLoading(false);
    }
  }, [token, siralama, sadeceBenim]);

  useEffect(() => { yukle(); }, [yukle, refreshTrigger]);

  const yayinAc = async () => {
    setYayinAcik(true);
    setYayinHata(null);
    if (stoklar.length === 0) {
      try {
        const res = await fetch(`${API_BASE}/stocks`);
        if (res.ok) {
          const liste: StockOption[] = await res.json();
          setStoklar(liste.filter((s) => s.current_price > 0));
        }
      } catch (err) {
        console.error("Hisse listesi alınamadı:", err);
      }
    }
  };

  const toplamAgirlik = useMemo(
    () => satirlar.reduce((t, r) => t + (Number.parseFloat(r.weight) || 0), 0),
    [satirlar],
  );

  const satirGuncelle = (i: number, alan: keyof DraftRow, deger: string) =>
    setSatirlar((s) => s.map((r, k) => (k === i ? { ...r, [alan]: deger } : r)));

  const esitDagit = () => {
    const dolu = satirlar.filter((r) => r.symbol.trim()).length;
    if (dolu === 0) return;
    const pay = Math.floor((10000 / dolu)) / 100;
    let kalan = 100;
    let goruldu = 0;
    setSatirlar(satirlar.map((r) => {
      if (!r.symbol.trim()) return r;
      goruldu += 1;
      const w = goruldu === dolu ? Math.round(kalan * 100) / 100 : pay;
      kalan -= w;
      return { ...r, weight: String(w) };
    }));
  };

  const yayinla = async () => {
    if (!token) return;
    const items = satirlar
      .filter((r) => r.symbol.trim())
      .map((r) => ({ symbol: r.symbol.trim().toUpperCase(), weight_pct: Number.parseFloat(r.weight) }));
    if (isim.trim().length < 3) return setYayinHata("Sepet adı en az 3 karakter olmalı.");
    if (items.length < 2) return setYayinHata("En az 2 hisse eklemelisiniz.");
    if (items.some((i) => !Number.isFinite(i.weight_pct) || i.weight_pct <= 0)) return setYayinHata("Her hisse için 0'dan büyük bir ağırlık girin.");
    if (Math.abs(toplamAgirlik - 100) > 0.01) return setYayinHata("Ağırlıkların toplamı %100 olmalı.");

    setYayinYukleniyor(true);
    setYayinHata(null);
    try {
      const res = await fetch(`${API_BASE}/marketplace`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: isim.trim(), description: aciklama.trim() || null, items }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        setYayinAcik(false);
        setIsim(""); setAciklama("");
        setSatirlar([{ symbol: "", weight: "" }, { symbol: "", weight: "" }]);
        setSonuc({ text: "Sepetiniz yayınlandı. Getiri, bu andan itibaren izlenecek.", isError: false });
        await yukle();
      } else {
        const d = data.detail;
        setYayinHata(typeof d === "string" ? d : Array.isArray(d) ? (d[0]?.msg ?? "Geçersiz bilgi.") : "Yayınlanamadı.");
      }
    } catch {
      setYayinHata("İşlem sırasında hata oluştu.");
    } finally {
      setYayinYukleniyor(false);
    }
  };

  const kopyala = async () => {
    if (!kopyalanan || !token) return;
    const miktar = Number.parseFloat(tutar);
    if (!Number.isFinite(miktar) || miktar <= 0) return setKopyaSonuc({ text: "Lütfen 0'dan büyük bir tutar girin.", isError: true });
    setKopyaYukleniyor(true);
    setKopyaSonuc(null);
    try {
      const res = await fetch(`${API_BASE}/marketplace/${kopyalanan.id}/copy`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ amount: miktar }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        let text = data.message as string;
        if (data.atlananlar?.length) text += ` Atlanan: ${data.atlananlar.join(", ")}.`;
        setKopyaSonuc({ text, isError: false });
        bumpRefresh();
      } else {
        const d = data.detail;
        setKopyaSonuc({ text: typeof d === "string" ? d : "Kopyalama başarısız.", isError: true });
      }
    } catch {
      setKopyaSonuc({ text: "İşlem sırasında hata oluştu.", isError: true });
    } finally {
      setKopyaYukleniyor(false);
    }
  };

  const sil = async (id: number) => {
    if (!token) return;
    if (silOnay !== id) {
      setSilOnay(id);
      setTimeout(() => setSilOnay((s) => (s === id ? null : s)), 4000);
      return;
    }
    setSilOnay(null);
    try {
      const res = await fetch(`${API_BASE}/marketplace/${id}`, { method: "DELETE", headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        setSonuc({ text: "Sepet kaldırıldı.", isError: false });
        await yukle();
      }
    } catch (err) {
      console.error("Sepet silinemedi:", err);
    }
  };

  const miktarSayi = Number.parseFloat(tutar);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {SIRALAMALAR.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setSiralama(id)}
            className={`min-h-[36px] px-3 rounded-lg text-[11px] font-bold flex items-center gap-1.5 border transition ${
              siralama === id ? "bg-[#242B35] border-[#3A4452] text-white" : "border-[#242B35] text-gray-400 hover:text-white"
            }`}
          >
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
        <button
          onClick={() => setSadeceBenim((v) => !v)}
          className={`min-h-[36px] px-3 rounded-lg text-[11px] font-bold border transition ${
            sadeceBenim ? "bg-[#F59E0B]/15 border-[#F59E0B]/40 text-[#F59E0B]" : "border-[#242B35] text-gray-400 hover:text-white"
          }`}
        >
          Sepetlerim
        </button>
        <button
          onClick={yayinAc}
          className="ml-auto min-h-[36px] px-3 rounded-lg bg-[#10B981] hover:bg-[#0FA271] text-[#0B0E14] text-[11px] font-bold flex items-center gap-1.5 transition"
        >
          <Plus className="w-3.5 h-3.5" /> Sepet Yayınla
        </button>
      </div>

      {sonuc && (
        <p className={`text-[11px] ${sonuc.isError ? "text-[#F43F5E]" : "text-[#10B981]"}`}>{sonuc.text}</p>
      )}

      {loading ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center">
          <p className="text-xs text-gray-500">Yükleniyor...</p>
        </div>
      ) : baskets.length === 0 ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center">
          <p className="text-xs text-gray-400">
            {sadeceBenim ? "Henüz yayınladığınız bir sepet yok." : "Pazaryerinde henüz sepet yok. İlk sepeti sen yayınla!"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {baskets.map((b) => (
            <div key={b.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-5 flex flex-col">
              <div className="flex items-start justify-between gap-3 mb-1">
                <div className="min-w-0">
                  <h3 className="text-sm font-bold text-white truncate">{b.name}</h3>
                  <p className="text-[10px] text-gray-500">
                    <Link href={`/profil/${b.owner_username}`} className="hover:text-gray-300">@{b.owner_username}</Link>
                    {" · "}{new Date(b.created_at + "Z").toLocaleDateString("tr-TR")}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <GetiriRozeti pct={b.getiri_pct} />
                  <p className="text-[9px] text-gray-600">yayından beri</p>
                </div>
              </div>
              {b.description && <p className="text-xs text-gray-500 mt-1 break-words">{b.description}</p>}

              <div className="flex flex-wrap gap-1.5 my-3">
                {b.items.map((it) => (
                  <Link
                    key={it.symbol}
                    href={`/hisse/${it.symbol}`}
                    className="text-[10px] font-semibold px-1.5 py-1 rounded bg-[#0B0E14] border border-[#242B35] text-gray-300 hover:text-white hover:border-gray-500 transition"
                  >
                    {it.symbol} <span className="text-gray-500">%{fmt(it.weight_pct)}</span>
                    {it.getiri_pct !== null && (
                      <span className={it.getiri_pct >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"}>
                        {" "}{it.getiri_pct >= 0 ? "+" : ""}{fmt(it.getiri_pct)}%
                      </span>
                    )}
                  </Link>
                ))}
              </div>

              <div className="mt-auto flex items-center gap-2">
                <span className="text-[10px] text-gray-500 flex items-center gap-1 mr-auto">
                  <Users className="w-3 h-3" /> {b.kopya_sayisi} kişi kopyaladı
                </span>
                {b.is_mine && (
                  <button
                    onClick={() => sil(b.id)}
                    className={`min-h-[40px] px-3 rounded-lg border text-[11px] font-bold flex items-center gap-1 transition ${
                      silOnay === b.id ? "border-[#F43F5E] text-[#F43F5E]" : "border-[#242B35] text-gray-400 hover:text-white"
                    }`}
                    aria-label="Sepeti kaldır"
                  >
                    <Trash2 className="w-3.5 h-3.5" /> {silOnay === b.id ? "Emin misin?" : "Kaldır"}
                  </button>
                )}
                <button
                  onClick={() => { setKopyalanan(b); setTutar("5000"); setKopyaSonuc(null); }}
                  className="min-h-[40px] px-3 rounded-lg bg-[#242B35] hover:bg-[#2E3641] text-white text-[11px] font-bold flex items-center gap-1.5 transition"
                >
                  <Copy className="w-3.5 h-3.5" /> Kopyala
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {kopyalanan && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 p-0 sm:p-4 overflow-y-auto">
          <div className="w-full sm:max-w-sm bg-[#151921] border border-[#242B35] rounded-t-2xl sm:rounded-2xl p-5 my-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white truncate">{kopyalanan.name}</h3>
              <button onClick={() => setKopyalanan(null)} className="min-w-[36px] min-h-[36px] flex items-center justify-center text-gray-400 hover:text-white" aria-label="Kapat">
                <X className="w-4 h-4" />
              </button>
            </div>
            <label className="block text-[11px] font-semibold text-gray-400 mb-1.5">Bu sepete ayıracağın tutar (sanal TL)</label>
            <input
              type="number" inputMode="decimal" min={1} value={tutar}
              onChange={(e) => setTutar(e.target.value)}
              className="w-full min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm font-semibold tabular-nums mb-3 focus:outline-none focus:border-[#F59E0B]"
            />
            <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3 mb-3 space-y-1">
              {kopyalanan.items.map((it) => (
                <div key={it.symbol} className="flex justify-between text-[11px]">
                  <span className="text-gray-300 font-semibold">{it.symbol} <span className="text-gray-500">%{fmt(it.weight_pct)}</span></span>
                  <span className="text-gray-400 tabular-nums">
                    {Number.isFinite(miktarSayi) && miktarSayi > 0 ? `${fmt((miktarSayi * it.weight_pct) / 100)} TL` : "—"}
                  </span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-gray-500 mb-3">
              Tutar, yayıncının ağırlıklarına göre dağıtılır ve piyasa fiyatından alınır (komisyon dahil).
              Kopyaladıktan sonra hisseler normal pozisyonların olur. Tamamen sanal bakiye.
            </p>
            {kopyaSonuc && (
              <p className={`text-[11px] mb-3 ${kopyaSonuc.isError ? "text-[#F43F5E]" : "text-[#10B981]"}`}>{kopyaSonuc.text}</p>
            )}
            <button
              onClick={kopyala} disabled={kopyaYukleniyor}
              className="w-full min-h-[44px] rounded-lg bg-[#10B981] hover:bg-[#0FA271] disabled:opacity-50 text-[#0B0E14] text-sm font-bold transition"
            >
              {kopyaYukleniyor ? "İşleniyor..." : "Kopyalamayı Onayla"}
            </button>
          </div>
        </div>
      )}

      {yayinAcik && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 p-0 sm:p-4 overflow-y-auto">
          <div className="w-full sm:max-w-md bg-[#151921] border border-[#242B35] rounded-t-2xl sm:rounded-2xl p-5 my-auto max-h-[92vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white">Sepet Yayınla</h3>
              <button onClick={() => setYayinAcik(false)} className="min-w-[36px] min-h-[36px] flex items-center justify-center text-gray-400 hover:text-white" aria-label="Kapat">
                <X className="w-4 h-4" />
              </button>
            </div>

            <input
              value={isim} onChange={(e) => setIsim(e.target.value)} maxLength={40} placeholder="Sepet adı"
              className="w-full min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm mb-2 focus:outline-none focus:border-[#F59E0B]"
            />
            <input
              value={aciklama} onChange={(e) => setAciklama(e.target.value)} maxLength={200} placeholder="Kısa açıklama (isteğe bağlı)"
              className="w-full min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm mb-3 focus:outline-none focus:border-[#F59E0B]"
            />

            <datalist id="mp-stoklar">
              {stoklar.map((s) => <option key={s.symbol} value={s.symbol}>{s.company_name}</option>)}
            </datalist>
            <div className="space-y-2 mb-3">
              {satirlar.map((r, i) => (
                <div key={i} className="flex gap-2">
                  <input
                    list="mp-stoklar" value={r.symbol} onChange={(e) => satirGuncelle(i, "symbol", e.target.value.toUpperCase())}
                    placeholder="Hisse (ör. THYAO)" maxLength={10}
                    className="flex-1 min-w-0 min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm focus:outline-none focus:border-[#F59E0B]"
                  />
                  <input
                    type="number" inputMode="decimal" value={r.weight} onChange={(e) => satirGuncelle(i, "weight", e.target.value)}
                    placeholder="%"
                    className="w-20 min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm tabular-nums focus:outline-none focus:border-[#F59E0B]"
                  />
                  {satirlar.length > 2 && (
                    <button
                      onClick={() => setSatirlar((s) => s.filter((_, k) => k !== i))}
                      className="min-w-[36px] min-h-[44px] flex items-center justify-center text-gray-500 hover:text-[#F43F5E]" aria-label="Satırı sil"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between mb-3">
              <div className="flex gap-2">
                {satirlar.length < 10 && (
                  <button onClick={() => setSatirlar((s) => [...s, { symbol: "", weight: "" }])} className="text-[11px] font-bold text-gray-300 hover:text-white">
                    + Hisse ekle
                  </button>
                )}
                <button onClick={esitDagit} className="text-[11px] font-bold text-[#F59E0B] hover:text-[#FBBF24]">Eşit dağıt</button>
              </div>
              <span className={`text-[11px] font-bold tabular-nums ${Math.abs(toplamAgirlik - 100) <= 0.01 ? "text-[#10B981]" : "text-[#F59E0B]"}`}>
                Toplam: %{fmt(toplamAgirlik)}
              </span>
            </div>

            <p className="text-[10px] text-gray-500 mb-3">
              Yayınladıktan sonra sepet değiştirilemez; getirisi bugünkü fiyatlardan itibaren herkese açık izlenir. Başkaları
              kopyalayınca oyun puanı kazanırsın.
            </p>
            {yayinHata && <p className="text-[11px] text-[#F43F5E] mb-3">{yayinHata}</p>}
            <button
              onClick={yayinla} disabled={yayinYukleniyor}
              className="w-full min-h-[44px] rounded-lg bg-[#10B981] hover:bg-[#0FA271] disabled:opacity-50 text-[#0B0E14] text-sm font-bold transition"
            >
              {yayinYukleniyor ? "Yayınlanıyor..." : "Yayınla"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
