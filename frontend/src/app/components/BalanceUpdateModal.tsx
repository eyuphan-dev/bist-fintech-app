"use client";

import React, { useState } from "react";
import { X, Wallet, Loader2, CheckCircle2, XCircle } from "lucide-react";

interface BalanceUpdateModalProps {
  title: string;
  description: string;
  currentBalance: number;
  endpoint: string;
  token: string;
  onClose: () => void;
  onSuccess: (newBalance: number) => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

/** Bakiye Güncelle / Sıfırlama modalı — hem kullanıcı hem kişisel bot bakiyesi için kullanılır. */
export default function BalanceUpdateModal({
  title,
  description,
  currentBalance,
  endpoint,
  token,
  onClose,
  onSuccess,
}: BalanceUpdateModalProps) {
  const [value, setValue] = useState<number>(currentBalance);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (newBalance: number) => {
    setLoading(true);
    setFeedback(null);
    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ new_balance: newBalance }),
      });
      const data = await res.json().catch(() => null);

      if (res.ok && data) {
        setFeedback({ type: "success", text: data.message || "Bakiye güncellendi." });
        onSuccess(data.virtual_balance);
        setTimeout(onClose, 1200);
      } else {
        setFeedback({ type: "error", text: (data && (data.detail || data.message)) || "Bakiye güncellenemedi." });
      }
    } catch {
      setFeedback({ type: "error", text: "Sunucuya bağlanılamadı." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-sm bg-[#151921] border border-[#242B35] rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#242B35]">
          <div className="flex items-center gap-2">
            <Wallet className="w-4 h-4 text-[#F59E0B]" />
            <h3 className="text-sm font-bold text-white">{title}</h3>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <p className="text-[11px] text-gray-400 leading-relaxed">{description}</p>

          <div>
            <label className="text-[10px] text-gray-500 uppercase font-semibold">Yeni Bakiye (TL)</label>
            <input
              type="number"
              min={0}
              step={1000}
              className="w-full mt-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#F59E0B] rounded-lg px-3 py-2 text-white text-sm tabular-nums outline-none transition"
              value={value}
              onChange={(e) => setValue(Math.max(0, Number(e.target.value) || 0))}
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => handleSubmit(100000)}
              disabled={loading}
              className="flex-1 bg-[#151921] border border-[#242B35] hover:border-[#F59E0B]/40 text-gray-300 text-[11px] font-semibold py-2 rounded-lg transition disabled:opacity-50"
            >
              100.000 TL'ye Sıfırla
            </button>
            <button
              onClick={() => handleSubmit(value)}
              disabled={loading}
              className="flex-1 bg-[#F59E0B] hover:bg-[#d98a08] text-[#0B0E14] font-bold text-[11px] py-2 rounded-lg transition disabled:opacity-50 flex items-center justify-center gap-1.5"
            >
              {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Kaydet
            </button>
          </div>

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
        </div>
      </div>
    </div>
  );
}
