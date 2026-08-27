"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw, Star, StarOff } from "lucide-react";
import KatilimBadge from "../components/KatilimBadge";
import { useAuth, API_BASE } from "../context/AuthContext";
import { marketBadgeClass } from "../../lib/marketColor";

interface WatchlistItem {
  symbol: string;
  company_name: string;
  current_price: number;
  price_change_pct: number | null;
  is_katilim_compliant: boolean;
  katilim_status?: string | null;
  purification_rate: number;
  added_at: string;
  target_price: number | null;
  note: string | null;
  distance_to_target_pct: number | null;
}

export default function FavorilerPage() {
  const { token, refreshTrigger } = useAuth();
  // Hedef fiyat / not düzenlemesi — hangi sembol açık ve taslak değerler.
  const [editing, setEditing] = useState<string | null>(null);
  const [draftTarget, setDraftTarget] = useState("");
  const [draftNote, setDraftNote] = useState("");
  const [saving, setSaving] = useState(false);

  const openEditor = (item: WatchlistItem) => {
    setEditing(item.symbol);
    setDraftTarget(item.target_price !== null ? String(item.target_price) : "");
    setDraftNote(item.note ?? "");
  };

  const saveEditor = async (symbol: string) => {
    if (!token || saving) return;
    setSaving(true);
    try {
      const hasTarget = draftTarget.trim() !== "";
      const hasNote = draftNote.trim() !== "";
      const res = await fetch(`${API_BASE}/watchlist/${symbol}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          // Boş bırakmak "temizle" demektir; API'de null göndermek "değiştirme"
          // anlamına geldiği için ayrı bayrak kullanılır.
          target_price: hasTarget ? Number(draftTarget) : null,
          clear_target: !hasTarget,
          note: hasNote ? draftNote : null,
          clear_note: !hasNote,
        }),
      });
      if (res.ok) {
        const updated: WatchlistItem = await res.json();
        setItems((prev) =>
          prev.map((x) => (x.symbol === symbol
            ? { ...x, target_price: updated.target_price, note: updated.note,
                distance_to_target_pct: updated.distance_to_target_pct }
            : x))
        );
        setEditing(null);
      }
    } catch (err) {
      console.error("Hedef fiyat kaydedilemedi:", err);
    } finally {
      setSaving(false);
    }
  };

  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [removing, setRemoving] = useState<string | null>(null);

  const fetchWatchlist = async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/watchlist`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setItems(await res.json());
    } catch (err) {
      console.error("İzleme listesi alınamadı:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchWatchlist();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, refreshTrigger]);

  const handleRemove = async (symbol: string) => {
    if (!token) return;
    setRemoving(symbol);
    try {
      const res = await fetch(`${API_BASE}/watchlist/${symbol}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setItems((prev) => prev.filter((i) => i.symbol !== symbol));
    } catch (err) {
      console.error("İzleme listesinden çıkarılamadı:", err);
    } finally {
      setRemoving(null);
    }
  };

  if (!token) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-16 text-center text-gray-500 text-sm">
        Favori hisselerinizi görmek için giriş yapmalısınız.
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Star className="w-5 h-5 text-[#F59E0B]" /> Favorilerim
        </h1>
        <p className="text-xs text-gray-500 mt-1">İzlemek için yıldızladığınız hisseler burada listelenir.</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#4A87C7]" />
          Favoriler yükleniyor...
        </div>
      ) : items.length === 0 ? (
        <div className="text-center text-gray-500 text-xs py-16 space-y-2">
          <p>Henüz favori hisseniz yok.</p>
          <Link href="/piyasalar" className="text-[#4A87C7] font-semibold hover:text-[#34d399]">
            Piyasalara göz atın →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <div
              key={item.symbol}
              className="bg-[#151921] p-4 rounded-2xl border border-[#242B35] hover:border-[#4A87C7]/40 transition flex flex-col gap-3 relative"
            >
              <button
                onClick={() => handleRemove(item.symbol)}
                disabled={removing === item.symbol}
                title="Favorilerden çıkar"
                className="absolute top-3 right-3 text-[#F59E0B] hover:text-[#F43F5E] transition disabled:opacity-50"
              >
                {removing === item.symbol ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <StarOff className="w-4 h-4" />
                )}
              </button>

              <Link href={`/hisse/${item.symbol}`} className="flex flex-col gap-3">
                <div className="flex items-start justify-between pr-6">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-white tracking-wide">{item.symbol}</span>
                      {item.price_change_pct !== null ? (
                        <span className={`text-[10px] font-semibold px-1 rounded tabular-nums ${
                          marketBadgeClass(item.price_change_pct)
                        }`}>
                          %{item.price_change_pct > 0 ? "+" : ""}{item.price_change_pct}
                        </span>
                      ) : (
                        <span className="text-[10px] font-semibold px-1 rounded tabular-nums bg-gray-500/10 text-gray-500">—</span>
                      )}
                    </div>
                    <p className="text-[11px] text-gray-500 mt-0.5 truncate max-w-[180px]">{item.company_name}</p>
                  </div>
                  <p className="font-bold text-sm text-white tabular-nums">{item.current_price} TL</p>
                </div>

                <KatilimBadge isCompliant={item.is_katilim_compliant} status={item.katilim_status} purificationRate={item.purification_rate} size="sm" />
              </Link>

              {/* Hedef fiyat & not */}
              {editing === item.symbol ? (
                <div className="space-y-2 border-t border-[#242B35] pt-3">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={draftTarget}
                    onChange={(e) => setDraftTarget(e.target.value)}
                    placeholder="Hedef fiyat (TL)"
                    className="w-full bg-[#0B0E14] border border-[#242B35] focus:border-[#4A87C7] rounded-lg px-2.5 py-2.5 text-xs text-white outline-none"
                  />
                  <input
                    type="text"
                    maxLength={280}
                    value={draftNote}
                    onChange={(e) => setDraftNote(e.target.value)}
                    placeholder="Not (örn. bilanço sonrası tekrar bak)"
                    className="w-full bg-[#0B0E14] border border-[#242B35] focus:border-[#4A87C7] rounded-lg px-2.5 py-2.5 text-xs text-white outline-none"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => saveEditor(item.symbol)}
                      disabled={saving}
                      type="button"
                      className="flex-1 bg-[#4A87C7] hover:bg-[#0da271] text-[#0B0E14] font-bold text-[11px] py-2.5 rounded-lg transition disabled:opacity-50"
                    >
                      {saving ? "Kaydediliyor..." : "Kaydet"}
                    </button>
                    <button
                      onClick={() => setEditing(null)}
                      type="button"
                      className="px-3 py-2.5 rounded-lg text-[11px] font-semibold bg-[#0B0E14] border border-[#242B35] text-gray-400 hover:text-white transition"
                    >
                      Vazgeç
                    </button>
                  </div>
                </div>
              ) : (
                <div className="border-t border-[#242B35] pt-2.5 space-y-1">
                  {item.target_price !== null ? (
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-gray-500">Hedefim</span>
                      <span className="tabular-nums">
                        <span className="font-bold text-white">{item.target_price} TL</span>
                        {item.distance_to_target_pct !== null && (
                          <span
                            className="ml-1.5 text-[10px]"
                            style={{ color: item.distance_to_target_pct > 0 ? "#10B981" : "#F43F5E" }}
                            title={item.distance_to_target_pct > 0
                              ? "Hedef güncel fiyatın üstünde"
                              : "Güncel fiyat hedefi geçti"}
                          >
                            {item.distance_to_target_pct > 0 ? "+" : ""}
                            %{item.distance_to_target_pct}
                          </span>
                        )}
                      </span>
                    </div>
                  ) : (
                    <p className="text-[10px] text-gray-600">Hedef fiyat belirlenmedi.</p>
                  )}
                  {item.note && (
                    <p className="text-[10px] text-gray-400 italic break-words">&ldquo;{item.note}&rdquo;</p>
                  )}
                  <button
                    onClick={() => openEditor(item)}
                    type="button"
                    className="text-[10px] font-semibold text-[#F59E0B] hover:underline py-2 md:py-0"
                  >
                    {item.target_price !== null || item.note ? "Düzenle" : "Hedef fiyat / not ekle"}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
