"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Clock, Pencil, X, CheckCircle2, Loader2 } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";
import { formatIstanbulDateTime } from "../lib/formatDate";

interface PendingOrder {
  id: number;
  symbol: string;
  order_type: "LIMIT_BUY" | "LIMIT_SELL" | "STOP_LOSS_SELL" | "SCHEDULED_BUY";
  quantity: number;
  target_price: number | null;
  execution_time: string | null;
  status: string;
  fail_reason: string | null;
  created_at: string;
  executed_at: string | null;
}

const ORDER_TYPE_LABELS: Record<string, string> = {
  LIMIT_BUY: "Limit Alış",
  LIMIT_SELL: "Limit Satış",
  STOP_LOSS_SELL: "Zarar Kes",
  SCHEDULED_BUY: "Zamanlı Alış",
};

/** datetime-local input'u için ISO zaman damgasını TARAYICININ yerel saatiyle "YYYY-MM-DDTHH:mm" biçimine çevirir. */
function toDatetimeLocalValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Ana Portföy sayfasında "Hisse Pozisyonlarım" tablosunun hemen altında gösterilen,
 * kullanıcının TÜM hisselerdeki bekleyen (PENDING) Limit/Zamanlı emirlerini listeleyen,
 * düzenlemeye ve iptale izin veren bölüm.
 */
export default function PendingOrdersSection() {
  const { token } = useAuth();
  const [orders, setOrders] = useState<PendingOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const [editingOrder, setEditingOrder] = useState<PendingOrder | null>(null);
  const [editQuantity, setEditQuantity] = useState<number>(1);
  const [editTargetPrice, setEditTargetPrice] = useState<number>(0);
  const [editExecutionTime, setEditExecutionTime] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const fetchOrders = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/orders`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) {
        const all: PendingOrder[] = await res.json();
        setOrders(all.filter((o) => o.status === "PENDING"));
      }
    } catch (err) {
      console.error("Bekleyen emirler alınamadı:", err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  const openEditModal = (order: PendingOrder) => {
    setEditingOrder(order);
    setEditQuantity(order.quantity);
    setEditTargetPrice(order.target_price ?? 0);
    setEditExecutionTime(order.execution_time ? toDatetimeLocalValue(order.execution_time) : "");
    setEditError(null);
  };

  const handleSaveEdit = async () => {
    if (!token || !editingOrder) return;
    setSavingEdit(true);
    setEditError(null);
    try {
      const payload: Record<string, unknown> = { quantity: editQuantity };
      if (editingOrder.order_type === "SCHEDULED_BUY") {
        if (!editExecutionTime) {
          setEditError("Lütfen bir tarih/saat seçin.");
          setSavingEdit(false);
          return;
        }
        payload.execution_time = new Date(editExecutionTime).toISOString();
      } else {
        payload.target_price = editTargetPrice;
      }

      const res = await fetch(`${API_BASE}/orders/${editingOrder.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok) {
        setOrders((prev) => prev.map((o) => (o.id === data.id ? data : o)));
        setEditingOrder(null);
        setToast("Emir başarıyla güncellendi.");
      } else {
        setEditError(data.detail || "Emir güncellenemedi.");
      }
    } catch {
      setEditError("Sunucuya bağlanılamadı. Emir güncellenemedi.");
    } finally {
      setSavingEdit(false);
    }
  };

  const handleCancel = async (orderId: number) => {
    if (!token) return;
    if (!window.confirm("Bu emri iptal etmek istediğinize emin misiniz?")) return;
    setCancellingId(orderId);
    try {
      const res = await fetch(`${API_BASE}/orders/${orderId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setOrders((prev) => prev.filter((o) => o.id !== orderId));
        setToast("Emir başarıyla iptal edildi.");
      }
    } catch (err) {
      console.error("Emir iptal edilemedi:", err);
    } finally {
      setCancellingId(null);
    }
  };

  if (!token) return null;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
      {toast && (
        <div className="flex items-center gap-2 bg-[#10B981]/10 border border-[#10B981]/25 text-[#10B981] rounded-lg px-3 py-2 text-[11px] font-medium mb-4">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          {toast}
        </div>
      )}

      <h3 className="text-sm font-bold text-white tracking-wide uppercase mb-4 flex items-center gap-1.5">
        <Clock className="w-4 h-4 text-[#F59E0B]" /> Bekleyen Emirlerim
      </h3>

      {loading ? (
        <div className="flex items-center justify-center py-8 text-gray-500 text-xs">
          <Loader2 className="w-4 h-4 animate-spin mr-2 text-[#F59E0B]" />
          Emirler yükleniyor...
        </div>
      ) : orders.length === 0 ? (
        <p className="text-center py-8 text-gray-500 text-xs">
          Henüz aktif veya bekleyen bir emriniz bulunmuyor.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-gray-400 border-b border-[#242B35]">
                <th className="pb-3 font-semibold">Sembol</th>
                <th className="pb-3 font-semibold">Emir Tipi</th>
                <th className="pb-3 font-semibold">Adet</th>
                <th className="pb-3 font-semibold">Hedef/Tetik Fiyatı</th>
                <th className="pb-3 font-semibold whitespace-nowrap">Emir Tarihi/Saati</th>
                <th className="pb-3 font-semibold">Durum</th>
                <th className="pb-3 font-semibold text-right">İşlemler</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#242B35]/60">
              {orders.map((o) => (
                <tr key={o.id} className="hover:bg-[#0B0E14]/60 transition">
                  <td className="py-3 font-bold text-white">
                    <Link href={`/hisse/${o.symbol}`} className="hover:text-[#10B981] transition">
                      {o.symbol}
                    </Link>
                  </td>
                  <td className="py-3 text-gray-300">{ORDER_TYPE_LABELS[o.order_type] || o.order_type}</td>
                  <td className="py-3 text-gray-300 tabular-nums">{o.quantity}</td>
                  <td className="py-3 text-gray-300 tabular-nums">
                    {o.target_price !== null ? `${o.target_price} TL` : "Piyasa Fiyatı"}
                  </td>
                  <td className="py-3 text-gray-400 tabular-nums whitespace-nowrap text-[11px]">
                    {o.execution_time ? formatIstanbulDateTime(o.execution_time) : formatIstanbulDateTime(o.created_at)}
                  </td>
                  <td className="py-3">
                    <span className="text-[10px] font-bold px-2 py-1 rounded-md border bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/25">
                      Bekliyor
                    </span>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEditModal(o)}
                        title="Düzenle"
                        className="text-gray-400 hover:text-[#10B981] transition rounded-lg min-w-[36px] min-h-[36px] flex items-center justify-center"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleCancel(o.id)}
                        disabled={cancellingId === o.id}
                        title="İptal Et"
                        className="text-gray-400 hover:text-[#F43F5E] transition rounded-lg min-w-[36px] min-h-[36px] flex items-center justify-center disabled:opacity-50"
                      >
                        {cancellingId === o.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editingOrder && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setEditingOrder(null)}
        >
          <div
            className="relative w-full max-w-sm bg-[#151921] border border-[#242B35] rounded-2xl shadow-2xl p-5 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-white">
                {editingOrder.symbol} — {ORDER_TYPE_LABELS[editingOrder.order_type]} Düzenle
              </h4>
              <button onClick={() => setEditingOrder(null)} className="text-gray-500 hover:text-white transition">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400 font-medium">Adet:</span>
              <input
                type="number"
                min="1"
                step="1"
                className="bg-[#0B0E14] border border-[#242B35] rounded px-2.5 py-1.5 text-white w-24 text-center outline-none focus:border-[#10B981] font-semibold tabular-nums"
                value={editQuantity}
                onChange={(e) => setEditQuantity(Math.max(1, parseFloat(e.target.value) || 1))}
              />
            </div>

            {editingOrder.order_type === "SCHEDULED_BUY" ? (
              <div className="flex items-center justify-between text-xs gap-2">
                <span className="text-gray-400 font-medium shrink-0">Tarih/Saat:</span>
                <input
                  type="datetime-local"
                  className="bg-[#0B0E14] border border-[#242B35] rounded px-2.5 py-1.5 text-white outline-none focus:border-[#10B981] text-xs flex-1"
                  value={editExecutionTime}
                  onChange={(e) => setEditExecutionTime(e.target.value)}
                />
              </div>
            ) : (
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-400 font-medium">Hedef Fiyat:</span>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  className="bg-[#0B0E14] border border-[#242B35] rounded px-2.5 py-1.5 text-white w-28 text-center outline-none focus:border-[#10B981] font-semibold tabular-nums"
                  value={editTargetPrice}
                  onChange={(e) => setEditTargetPrice(parseFloat(e.target.value) || 0)}
                />
              </div>
            )}

            {editError && <p className="text-[11px] font-semibold text-[#F43F5E]">{editError}</p>}

            <button
              onClick={handleSaveEdit}
              disabled={savingEdit}
              className="w-full bg-[#10B981] hover:bg-[#0da271] text-[#0B0E14] font-bold py-2.5 rounded-lg text-xs transition disabled:opacity-50 flex items-center justify-center gap-1.5 min-h-[44px]"
            >
              {savingEdit && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Kaydet
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
