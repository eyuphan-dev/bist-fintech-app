"use client";

import React, { useEffect, useState } from "react";
import { Store, RefreshCw, Star, Check, Loader2 } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface ShopItem {
  id: string;
  isim: string;
  aciklama: string;
  kategori: "CERCEVE" | "UNVAN";
  maliyet: number;
  deger: string;
  sahip_mi: boolean;
  takili_mi: boolean;
}

export default function ShopPage() {
  const { token, loading: authLoading } = useAuth();
  const [items, setItems] = useState<ShopItem[]>([]);
  const [gamePoints, setGamePoints] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const fetchAll = async () => {
    if (!token) return;
    try {
      const [sRes, pRes] = await Promise.all([
        fetch(`${API_BASE}/shop`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/user/game-points`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (sRes.ok) setItems(await sRes.json());
      if (pRes.ok) setGamePoints((await pRes.json()).game_points);
    } catch (err) {
      console.error("Mağaza alınamadı:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(t);
  }, [toast]);

  const buy = async (item: ShopItem) => {
    if (!token) return;
    setBusyId(item.id);
    try {
      const res = await fetch(`${API_BASE}/shop/${item.id}/buy`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) {
        setToast(`${item.isim} satın alındı!`);
        fetchAll();
      } else {
        setToast(data.detail || "Satın alınamadı.");
      }
    } catch {
      setToast("Sunucuya bağlanılamadı.");
    } finally {
      setBusyId(null);
    }
  };

  const toggleEquip = async (item: ShopItem) => {
    if (!token) return;
    setBusyId(item.id);
    try {
      const yol = item.takili_mi ? "unequip" : "equip";
      const res = await fetch(`${API_BASE}/shop/${item.id}/${yol}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setToast(item.takili_mi ? `${item.isim} çıkarıldı.` : `${item.isim} takıldı.`);
        fetchAll();
      }
    } catch {
      setToast("Sunucuya bağlanılamadı.");
    } finally {
      setBusyId(null);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <RefreshCw className="w-10 h-10 text-[#10B981] animate-spin mb-4" />
        <p className="text-gray-400 font-medium">Yükleniyor...</p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 text-center">
          <p className="text-xs text-gray-400">Mağazayı görmek için giriş yapmalısın.</p>
        </div>
      </div>
    );
  }

  const cerceveler = items.filter((i) => i.kategori === "CERCEVE");
  const unvanlar = items.filter((i) => i.kategori === "UNVAN");

  const Kart = ({ item }: { item: ShopItem }) => (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex items-center gap-3">
      {item.kategori === "CERCEVE" ? (
        <span className="w-11 h-11 rounded-full shrink-0 border-2" style={{ borderColor: item.deger }} />
      ) : (
        <span
          className="text-[10px] font-bold px-2 py-1 rounded-full border shrink-0 whitespace-nowrap"
          style={{ color: "#C46D2C", borderColor: "rgba(196,109,44,0.3)", background: "rgba(196,109,44,0.1)" }}
        >
          {item.deger}
        </span>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-white">{item.isim}</p>
        <p className="text-[11px] text-gray-500 mt-0.5">{item.aciklama}</p>
      </div>
      <div className="shrink-0">
        {!item.sahip_mi ? (
          <button
            onClick={() => buy(item)}
            disabled={busyId === item.id || (gamePoints ?? 0) < item.maliyet}
            className="min-h-[36px] px-3 rounded-lg bg-[#10B981] hover:bg-[#0da271] text-[#0B0E14] text-xs font-bold transition disabled:opacity-40 flex items-center gap-1"
          >
            {busyId === item.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Star className="w-3.5 h-3.5" />}
            {item.maliyet}
          </button>
        ) : (
          <button
            onClick={() => toggleEquip(item)}
            disabled={busyId === item.id}
            className={`min-h-[36px] px-3 rounded-lg text-xs font-bold transition disabled:opacity-40 flex items-center gap-1 ${
              item.takili_mi ? "bg-[#242B35] text-white" : "bg-[#0B0E14] border border-[#242B35] text-gray-300 hover:text-white"
            }`}
          >
            {item.takili_mi && <Check className="w-3.5 h-3.5" />}
            {item.takili_mi ? "Takılı" : "Tak"}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      {toast && (
        <div className="fixed top-4 right-4 z-50 bg-[#151921] border border-[#242B35] rounded-lg px-4 py-2.5 text-xs text-white">
          {toast}
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Store className="w-5 h-5 text-[#F59E0B]" /> Sanal Ödül Mağazası
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Görevlerden ve Şampiyonlar Duvarı'ndan kazandığın oyun puanıyla
            profilini süsleyecek kozmetikler al. Gerçek parayla ilgisi yoktur.
          </p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">Oyun Puanı</p>
          <p className="text-lg font-bold text-[#F59E0B] tabular-nums">{gamePoints ?? "—"}</p>
        </div>
      </div>

      {loading ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center">
          <p className="text-xs text-gray-500">Yükleniyor...</p>
        </div>
      ) : (
        <>
          <div>
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-2">Çerçeveler</h3>
            <div className="space-y-2">
              {cerceveler.map((item) => <Kart key={item.id} item={item} />)}
            </div>
          </div>
          <div>
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-2">Unvanlar</h3>
            <div className="space-y-2">
              {unvanlar.map((item) => <Kart key={item.id} item={item} />)}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
