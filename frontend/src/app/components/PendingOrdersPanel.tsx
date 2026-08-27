"use client";

import React, { useEffect, useState } from "react";
import { Clock, Target, X, Plus } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";
import { formatIstanbulDateTime } from "../lib/formatDate";

interface PendingOrder {
  id: number;
  symbol: string;
  order_type: string;
  quantity: number;
  target_price: number | null;
  execution_time: string | null;
  status: string;
  fail_reason: string | null;
  created_at: string;
  executed_at: string | null;
}

const ORDER_TYPES = ["LIMIT_BUY", "LIMIT_SELL", "STOP_LOSS_SELL", "SCHEDULED_BUY"] as const;

const ORDER_TYPE_LABELS: Record<string, string> = {
  LIMIT_BUY: "Limit Alış",
  LIMIT_SELL: "Limit Satış",
  STOP_LOSS_SELL: "Zarar Kes",
  SCHEDULED_BUY: "Zamanlı Alış",
};

const STATUS_LABELS: Record<string, string> = {
  EXECUTED: "Gerçekleşti",
  FAILED: "Başarısız",
  CANCELLED: "İptal",
};

export default function PendingOrdersPanel({ symbol, currentPrice }: { symbol: string; currentPrice: number }) {
  const { token } = useAuth();
  const [orders, setOrders] = useState<PendingOrder[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [orderType, setOrderType] = useState<(typeof ORDER_TYPES)[number]>("LIMIT_BUY");
  const [quantity, setQuantity] = useState(1);
  const [targetPrice, setTargetPrice] = useState<number>(currentPrice);
  const [executionTime, setExecutionTime] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null);

  const fetchOrders = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/orders`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setOrders(await res.json());
    } catch (err) {
      console.error("Emirler alınamadı:", err);
    }
  };

  useEffect(() => {
    fetchOrders();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const symbolOrders = orders.filter((o) => o.symbol === symbol);
  const pendingOrders = symbolOrders.filter((o) => o.status === "PENDING");
  const historyOrders = symbolOrders.filter((o) => o.status !== "PENDING").slice(0, 5);

  const handleCreate = async () => {
    if (!token) return;
    setLoading(true);
    setMessage(null);
    try {
      const payload: Record<string, unknown> = { symbol, order_type: orderType, quantity };
      if (orderType === "SCHEDULED_BUY") {
        if (!executionTime) {
          setMessage({ text: "Lütfen bir tarih/saat seçin.", isError: true });
          setLoading(false);
          return;
        }
        payload.execution_time = new Date(executionTime).toISOString();
      } else {
        payload.target_price = targetPrice;
      }

      const res = await fetch(`${API_BASE}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ text: "Emir oluşturuldu.", isError: false });
        setShowForm(false);
        fetchOrders();
      } else {
        setMessage({ text: data.detail || "Emir oluşturulamadı.", isError: true });
      }
    } catch {
      setMessage({ text: "Emir oluşturulurken hata oluştu.", isError: true });
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (orderId: number) => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/orders/${orderId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) fetchOrders();
    } catch (err) {
      console.error("Emir iptal edilemedi:", err);
    }
  };

  if (!token) return null;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
          <Clock className="w-4 h-4 text-[#F59E0B]" /> Limit / Zamanlı Emirler
        </h3>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="text-[#4A87C7] hover:text-[#34d399] transition rounded-lg min-w-[44px] min-h-[44px] flex items-center justify-center"
          aria-label="Yeni emir ekle"
        >
          <Plus className="w-4 h-4" />
        </button>
      </div>

      {showForm && (
        <div className="space-y-2.5 bg-[#0B0E14] border border-[#242B35] rounded-xl p-3">
          <div className="grid grid-cols-3 gap-1.5">
            {ORDER_TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setOrderType(t)}
                className={`py-2.5 rounded-lg text-[10px] font-bold transition min-h-[44px] ${
                  orderType === t ? "bg-[#4A87C7] text-[#0B0E14]" : "bg-[#151921] text-gray-400 border border-[#242B35]"
                }`}
              >
                {ORDER_TYPE_LABELS[t]}
              </button>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400 font-medium">Miktar:</span>
            <input
              type="number"
              min="1"
              step="1"
              className="bg-[#151921] border border-[#242B35] rounded px-2.5 py-1.5 text-white w-20 text-center outline-none focus:border-[#4A87C7] font-semibold tabular-nums"
              value={quantity}
              onChange={(e) => setQuantity(Math.max(1, parseFloat(e.target.value) || 1))}
            />
          </div>

          {orderType === "SCHEDULED_BUY" ? (
            <div className="flex items-center justify-between text-xs gap-2">
              <span className="text-gray-400 font-medium shrink-0">Tarih/Saat:</span>
              <input
                type="datetime-local"
                className="bg-[#151921] border border-[#242B35] rounded px-2.5 py-1.5 text-white outline-none focus:border-[#4A87C7] text-xs flex-1"
                value={executionTime}
                onChange={(e) => setExecutionTime(e.target.value)}
              />
            </div>
          ) : (
            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400 font-medium flex items-center gap-1">
                <Target className="w-3 h-3" /> Hedef Fiyat:
              </span>
              <input
                type="number"
                min="0.01"
                step="0.01"
                className="bg-[#151921] border border-[#242B35] rounded px-2.5 py-1.5 text-white w-24 text-center outline-none focus:border-[#4A87C7] font-semibold tabular-nums"
                value={targetPrice}
                onChange={(e) => setTargetPrice(parseFloat(e.target.value) || 0)}
              />
            </div>
          )}

          <p className="text-[10px] text-gray-500 leading-relaxed">
            {orderType === "LIMIT_BUY" && "Fiyat bu değere veya altına düşerse otomatik alım yapılır."}
            {orderType === "LIMIT_SELL" && "Fiyat bu değere veya üstüne çıkarsa otomatik satış yapılır (kâr al)."}
            {orderType === "STOP_LOSS_SELL" && "Fiyat bu değere veya altına DÜŞERSE otomatik satış yapılır (zararı sınırlar). Aynı pozisyona hem kâr-al hem zarar-kes koyabilirsiniz; biri gerçekleşince diğeri otomatik iptal olur."}
            {orderType === "SCHEDULED_BUY" && "Seçilen zaman geldiğinde (borsa açıkken) piyasa fiyatından alım yapılır."}
            {" "}
            Kontroller yalnızca borsa açıkken (hafta içi 10:00-18:15) birkaç dakikada bir çalışır.
          </p>

          {message && (
            <p className={`text-[11px] font-semibold ${message.isError ? "text-[#F43F5E]" : "text-[#10B981]"}`}>
              {message.text}
            </p>
          )}

          <button
            onClick={handleCreate}
            disabled={loading}
            className="w-full bg-[#4A87C7] hover:bg-[#0da271] text-[#0B0E14] font-bold py-2.5 rounded-lg text-xs transition disabled:opacity-50 min-h-[44px]"
          >
            Emri Oluştur
          </button>
        </div>
      )}

      {pendingOrders.length === 0 ? (
        <p className="text-[11px] text-gray-500 text-center py-2">Bu hisse için bekleyen emriniz yok.</p>
      ) : (
        <div className="space-y-2">
          {pendingOrders.map((o) => (
            <div key={o.id} className="flex items-center justify-between bg-[#0B0E14] border border-[#242B35] rounded-lg p-2.5 text-xs">
              <div>
                <span className="font-semibold text-white">{ORDER_TYPE_LABELS[o.order_type]}</span>
                <span className="block text-[10px] text-gray-500 tabular-nums">
                  {o.quantity} adet
                  {o.target_price ? ` @ ${o.target_price} TL` : ""}
                  {o.execution_time ? ` — ${formatIstanbulDateTime(o.execution_time)}` : ""}
                </span>
              </div>
              <button
                onClick={() => handleCancel(o.id)}
                className="text-gray-500 hover:text-[#F43F5E] transition rounded-lg min-w-[44px] min-h-[44px] flex items-center justify-center"
                aria-label="Emri iptal et"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {historyOrders.length > 0 && (
        <div className="pt-2 border-t border-[#242B35] space-y-1.5">
          <p className="text-[10px] text-gray-500 uppercase font-bold tracking-wide">Son Geçmiş</p>
          {historyOrders.map((o) => (
            <div key={o.id} className="flex items-center justify-between text-[10px] text-gray-500">
              <span>
                {ORDER_TYPE_LABELS[o.order_type]} — {o.quantity} adet
                {o.fail_reason ? ` (${o.fail_reason})` : ""}
              </span>
              <span
                className={
                  o.status === "EXECUTED" ? "text-[#10B981]" : o.status === "FAILED" ? "text-[#F43F5E]" : "text-gray-500"
                }
              >
                {STATUS_LABELS[o.status] || o.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
