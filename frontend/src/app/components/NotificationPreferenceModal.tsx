"use client";

import React, { useEffect, useState } from "react";
import { X, Bell, CheckCircle2, XCircle } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface NotificationPreferenceModalProps {
  symbol: string;
  currentPrice: number;
  onClose: () => void;
}

interface Preference {
  stock_symbol: string;
  price_above: number | null;
  price_below: number | null;
  pct_change_trigger: number | null;
  notify_kap: boolean;
  notify_ai_signal: boolean;
}

/**
 * Hisse detay sayfasındaki "Bildirim Oluştur" butonundan açılan alarm ayarları modalı.
 * Fiyat üstü/altı ve % değişim alarmları tek seferlik/günlük tetiklenir (bkz. backend
 * notifications.py); KAP ve AI sinyal anahtarları açık kaldığı sürece tekrar tetiklenebilir.
 */
export default function NotificationPreferenceModal({ symbol, currentPrice, onClose }: NotificationPreferenceModalProps) {
  const { token } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [priceAbove, setPriceAbove] = useState("");
  const [priceBelow, setPriceBelow] = useState("");
  const [pctChange, setPctChange] = useState("");
  const [notifyKap, setNotifyKap] = useState(false);
  const [notifyAiSignal, setNotifyAiSignal] = useState(false);
  const [hasExisting, setHasExisting] = useState(false);

  useEffect(() => {
    const fetchPreference = async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/notification-preference`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data: Preference | null = await res.json();
          if (data) {
            setHasExisting(true);
            setPriceAbove(data.price_above !== null ? String(data.price_above) : "");
            setPriceBelow(data.price_below !== null ? String(data.price_below) : "");
            setPctChange(data.pct_change_trigger !== null ? String(data.pct_change_trigger) : "");
            setNotifyKap(data.notify_kap);
            setNotifyAiSignal(data.notify_ai_signal);
          }
        }
      } catch (err) {
        console.error("Alarm tercihi alınamadı:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchPreference();
  }, [symbol, token]);

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/notification-preference`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          price_above: priceAbove ? parseFloat(priceAbove) : null,
          price_below: priceBelow ? parseFloat(priceBelow) : null,
          pct_change_trigger: pctChange ? parseFloat(pctChange) : null,
          notify_kap: notifyKap,
          notify_ai_signal: notifyAiSignal,
        }),
      });
      if (res.ok) {
        setHasExisting(true);
        setFeedback({ type: "success", text: "Alarm tercihiniz kaydedildi." });
      } else {
        const data = await res.json().catch(() => null);
        setFeedback({ type: "error", text: data?.detail || "Kaydedilemedi." });
      }
    } catch {
      setFeedback({ type: "error", text: "Sunucuya bağlanılamadı." });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/notification-preference`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setPriceAbove("");
        setPriceBelow("");
        setPctChange("");
        setNotifyKap(false);
        setNotifyAiSignal(false);
        setHasExisting(false);
        setFeedback({ type: "success", text: "Alarm kaldırıldı." });
      }
    } catch {
      setFeedback({ type: "error", text: "Sunucuya bağlanılamadı." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={onClose}>
      <div
        className="relative w-full max-w-md bg-[#151921] border border-[#242B35] rounded-2xl overflow-hidden max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="bg-[#F59E0B]/10 border-b border-[#F59E0B]/20 px-5 py-4 flex items-center justify-between shrink-0">
          <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
            <Bell className="w-4 h-4" /> {symbol} için Bildirim Ayarları
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition shrink-0" title="Kapat">
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading ? (
          <p className="text-xs text-gray-500 text-center py-10">Yükleniyor...</p>
        ) : (
          <div className="px-5 py-4 space-y-4 overflow-y-auto">
            <p className="text-[11px] text-gray-500">Güncel fiyat: {currentPrice.toFixed(2)} TL</p>

            <div>
              <label className="text-[10px] text-gray-400 uppercase font-bold tracking-widest">Fiyat Üst Limiti (TL)</label>
              <input
                type="number"
                step="0.01"
                value={priceAbove}
                onChange={(e) => setPriceAbove(e.target.value)}
                placeholder="örn. 100.00"
                className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#4A87C7] rounded-lg px-3 py-2 text-white text-sm outline-none transition"
              />
              <p className="text-[10px] text-gray-600 mt-1">Fiyat bu seviyeye ulaşınca bir kez bildirim alırsınız.</p>
            </div>

            <div>
              <label className="text-[10px] text-gray-400 uppercase font-bold tracking-widest">Fiyat Alt Limiti (TL)</label>
              <input
                type="number"
                step="0.01"
                value={priceBelow}
                onChange={(e) => setPriceBelow(e.target.value)}
                placeholder="örn. 80.00"
                className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#4A87C7] rounded-lg px-3 py-2 text-white text-sm outline-none transition"
              />
              <p className="text-[10px] text-gray-600 mt-1">Fiyat bu seviyenin altına inince bir kez bildirim alırsınız.</p>
            </div>

            <div>
              <label className="text-[10px] text-gray-400 uppercase font-bold tracking-widest">Günlük % Değişim Eşiği</label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={pctChange}
                onChange={(e) => setPctChange(e.target.value)}
                placeholder="örn. 5"
                className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#4A87C7] rounded-lg px-3 py-2 text-white text-sm outline-none transition"
              />
              <p className="text-[10px] text-gray-600 mt-1">Hisse gün içinde ± bu yüzdeden fazla hareket ederse (günde en fazla bir kez) bildirim alırsınız.</p>
            </div>

            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyKap}
                onChange={(e) => setNotifyKap(e.target.checked)}
                className="w-4 h-4 accent-[#4A87C7]"
              />
              <span className="text-xs text-gray-300">Yeni KAP bildirimi geldiğinde haber ver</span>
            </label>

            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyAiSignal}
                onChange={(e) => setNotifyAiSignal(e.target.checked)}
                className="w-4 h-4 accent-[#4A87C7]"
              />
              <span className="text-xs text-gray-300">AI strateji sinyali (AL/SAT) üretildiğinde haber ver</span>
            </label>

            {feedback && (
              <div
                className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-medium border ${
                  feedback.type === "success"
                    ? "bg-[#4A87C7]/10 border-[#4A87C7]/25 text-[#4A87C7]"
                    : "bg-[#F43F5E]/10 border-[#F43F5E]/25 text-[#F43F5E]"
                }`}
              >
                {feedback.type === "success" ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0" /> : <XCircle className="w-3.5 h-3.5 shrink-0" />}
                {feedback.text}
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 bg-[#4A87C7] hover:bg-[#0da271] text-[#0B0E14] font-bold text-xs py-2.5 rounded-lg transition disabled:opacity-50"
              >
                {saving ? "Kaydediliyor..." : "Kaydet"}
              </button>
              {hasExisting && (
                <button
                  onClick={handleDelete}
                  disabled={saving}
                  className="px-4 bg-[#151921] border border-[#F43F5E]/30 hover:bg-[#F43F5E]/10 text-[#F43F5E] font-bold text-xs py-2.5 rounded-lg transition disabled:opacity-50"
                >
                  Kaldır
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
